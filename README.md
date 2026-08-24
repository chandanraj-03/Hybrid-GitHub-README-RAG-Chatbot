# ⚡ README RAG Chatbot

An open-source, dual-tier Retrieval-Augmented Generation (RAG) system designed to answer questions about any public GitHub repository grounded strictly in its `README.md`.

**Zero Paid AI Services • GPU-Accelerated Local Indexing • Ultra-Lightweight Render Cloud Server**

---

## 📑 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Workflow Separation](#2-architecture--workflow-separation)
3. [Why Indexing is Performed Locally](#3-why-indexing-is-performed-locally)
4. [Why Local NVIDIA GPU is Used](#4-why-local-nvidia-gpu-is-used)
5. [Why Embeddings are Stored in Supabase](#5-why-embeddings-are-stored-in-supabase)
6. [Why pgvector is Used](#6-why-pgvector-is-used)
7. [Intelligent Markdown Chunking Strategy](#7-intelligent-markdown-chunking-strategy)
8. [Embedding Strategy & Model Flexibility](#8-embedding-strategy--model-flexibility)
9. [RAG Pipeline & Grounded Prompt](#9-rag-pipeline--grounded-prompt)
10. [Generation Model & Hallucination Control](#10-generation-model--hallucination-control)
11. [Local Indexing Setup & CLI Guide](#11-local-indexing-setup--cli-guide)
12. [NVIDIA GPU / CUDA Setup](#12-nvidia-gpu--cuda-setup)
13. [Supabase Setup Guide](#13-supabase-setup-guide)
14. [Database Schema & Stored RPC Functions](#14-database-schema--stored-rpc-functions)
15. [Render Deployment Guide](#15-render-deployment-guide)
16. [Environment Variables Reference](#16-environment-variables-reference)
17. [Frontend Integration Guide](#17-frontend-integration-guide)
18. [Re-indexing & Multi-Project Isolation](#18-re-indexing--multi-project-isolation)
19. [README Hash & Change Detection](#19-readme-hash--change-detection)
20. [Performance & Low-Memory Optimization](#20-performance--low-memory-optimization)
21. [Security Best Practices](#21-security-best-practices)
22. [Limitations](#22-limitations)
23. [Future Improvements & Model Upgrades](#23-future-improvements--model-upgrades)

---

## 1. Project Overview

The **README RAG Chatbot** solves the problem of querying GitHub documentation accurately without relying on expensive, rate-limited, or privacy-invasive third-party LLM APIs (OpenAI, Gemini, Claude, Groq, Ollama, etc.).

By decoupling the computationally heavy document processing and vector generation from query-time retrieval, the system achieves:
- **Fast, reliable GPU indexing** locally on your workstation.
- **Low-cost, low-memory cloud deployment** on Render (RAM < 512MB).
- **Strictly grounded answers** with zero hallucinations and full citation of markdown sections.

---

## 2. Architecture & Workflow Separation

The system is strictly partitioned into two distinct workflows:

```
========================================================================
WORKFLOW A: LOCAL LAPTOP WITH NVIDIA GPU (Heavy Preprocessing)
========================================================================

   GitHub Public URL (e.g. https://github.com/user/project)
                 │
                 ▼
         Fetch Raw README.md
                 │
                 ▼
         Calculate SHA-256 Hash  ───> Match existing hash in Supabase?
                 │                    └─> If identical: Skip (No re-indexing)
                 ▼
    Section-Aware Hierarchical Chunking
   (#, ##, ###, code blocks, tables, lists)
                 │
                 ▼
   Transformer Embedding Model (CUDA)
  (sentence-transformers/all-MiniLM-L6-v2)
                 │
                 ▼
       Precomputed Float Embeddings
                 │
                 ▼
   Upload Project Record + Chunks + Vectors
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│               SUPABASE DATABASE                 │
│         PostgreSQL + pgvector + HNSW            │
└─────────────────────────────────────────────────┘
                 ▲
                 │
========================================================================
WORKFLOW B: RENDER FASTAPI SERVER (Lightweight Query Serving)
========================================================================
                 │
        User Asks Question
                 │
                 ▼
    Question Embedding on CPU
  (sentence-transformers/all-MiniLM-L6-v2)
                 │
                 ▼
   Project-Isolated pgvector Search
  (match_readme_chunks RPC with threshold)
                 │
                 ▼
   Top 3-5 Relevant README Chunks
                 │
                 ▼
  Lightweight Generator (google/flan-t5-small)
  (torch.no_grad(), strict grounded prompt)
                 │
                 ▼
Natural-Language Answer + Cited Sources (▼ Section > Sub-section)
```

---

## 3. Why Indexing is Performed Locally

1. **Zero Cloud Worker Cost**: Heavy natural language document parsing, chunking, and Transformer inference require substantial CPU/GPU resources that are costly or strictly memory-capped in free/starter cloud hosting tiers (e.g. Render 512MB RAM).
2. **Deterministic Precomputation**: All repository chunking and embedding operations happen ahead-of-time. Query responses take milliseconds because the database already stores pre-calculated vectors.
3. **No Uncontrolled Web Scraping on Render**: The Render production server never clones repositories, parses raw Markdown, or downloads large files during runtime.

---

## 4. Why Local NVIDIA GPU is Used

- Generating high-dimensional vector embeddings for hundreds of README chunks can take dozens of seconds on CPU.
- With NVIDIA CUDA acceleration (e.g. RTX 3050/3060/4090), batch vectorization runs in milliseconds with parallel tensor execution (`device="cuda"`).
- The pipeline gracefully falls back to CPU if CUDA is unavailable.

---

## 5. Why Embeddings are Stored in Supabase

- Supabase provides a managed, scalable PostgreSQL database.
- Centralized storage allows multiple web clients and applications to query embeddings without maintaining local vector database files (like SQLite/FAISS binaries) in ephemeral cloud container filesystems.
- Robust ACID transactions allow atomic project re-indexing and cascading chunk deletions.

---

## 6. Why pgvector is Used

- `pgvector` adds vector similarity search directly into PostgreSQL.
- Using the `match_readme_chunks` RPC function with an HNSW index allows cosine similarity searches (`1 - (embedding <=> query_embedding)`) with millisecond response times.
- Eliminates the need for separate standalone vector databases (e.g. Pinecone, Qdrant).
- Enables strict relational filtering: search queries **never** leak across different projects (`WHERE project_id = match_project_id`).

---

## 7. Intelligent Markdown Chunking Strategy

Unlike naive character-splitting or arbitrary tokenizers that slice sentences in half, the custom `MarkdownChunker` in `indexer/markdown_chunker.py`:

1. **Recognizes Heading Hierarchies**: Understands `#`, `##`, `###`, `####`, `#####`, `######`.
2. **Maintains Section Breadcrumbs**: Every chunk retains its structural path (e.g., `Installation > Windows > Prerequisites`).
3. **Preserves Atomic Units**:
   - **Code Blocks**: Fenced blocks (```` ```bash ... ``` ````) are kept intact and not split mid-syntax.
   - **Markdown Tables**: Structured data rows and headers are preserved together.
   - **Bullet & Numbered Lists**: List groupings remain coherent.
4. **Handles Oversized Sections**: If a single subsection exceeds `CHUNK_SIZE` (default: 800 chars), it is split with a configurable `CHUNK_OVERLAP` (default: 150 chars) at word/sentence boundaries.

---

## 8. Embedding Strategy & Model Flexibility

- **Default Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- **Dynamic Dimension Detection**: The dimension is queried dynamically from the model (`model.get_sentence_embedding_dimension()`) and saved in the database record.
- **Upgradable**: You can switch to `BAAI/bge-base-en-v1.5` (768 dim) or other Sentence Transformers simply via `--model` flag or config without modifying core application code.
- **Normalized Vectors**: Embeddings are L2-normalized during generation for exact cosine similarity calculation using the `<=>` inner product operator.

---

## 9. RAG Pipeline & Grounded Prompt

When a user asks a question:
1. `QuestionEmbedder` vectorizes the query.
2. `ReadmeRetriever` executes the `match_readme_chunks` RPC on Supabase with the project UUID.
3. Chunks below `SIMILARITY_THRESHOLD` (default: 0.40) are discarded.
4. If valid context exists, the prompt is structured:

```text
You are a project documentation assistant.
Answer the user's question using ONLY the provided README context.
Do not use outside knowledge.
Do not invent information.
If the answer is not present in the provided README context, respond exactly:
"I couldn't find that information in the README.md."

README CONTEXT:
### Section: Installation > Prerequisites
Python 3.10+ and PyTorch are required.

QUESTION:
What are the installation requirements?

ANSWER:
```

---

## 10. Generation Model & Hallucination Control

- **Model**: `google/flan-t5-small` (~77M parameters, ~300MB RAM footprint).
- **Execution**: Pre-warmed once at FastAPI startup, runs strictly on CPU with `torch.no_grad()` and greedy beam search (`num_beams=2, max_new_tokens=128`).
- **Two-Tier Hallucination Shield**:
  1. *Score Gate*: If no retrieved chunk meets the similarity threshold, generation is skipped and the standard refusal `"I couldn't find that information in the README.md."` is returned immediately.
  2. *Refusal Normalization*: If the model outputs an ungrounded or ambiguous refusal, it is normalized to the exact refusal string.

---

## 11. Local Indexing Setup & CLI Guide

### Installation
Navigate to the `indexer` directory and install dependencies:

```powershell
cd indexer
pip install -r requirements-indexer.txt
```

Create your `indexer/.env` file:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

### CLI Commands

#### 1. Check GPU & CUDA Availability
```powershell
python index_project.py --gpu-info
```

#### 2. Index a GitHub Repository
```powershell
python index_project.py --github https://github.com/fastapi/fastapi
```

#### 3. Force Re-Indexing (Bypass Hash Check)
```powershell
python index_project.py --github https://github.com/fastapi/fastapi --force
```

#### 4. Dry Run (Test Chunking & Embeddings without Supabase Upload)
```powershell
python index_project.py --github https://github.com/psf/requests --dry-run
```

#### 5. Custom Model & Chunk Size
```powershell
python index_project.py --github https://github.com/owner/repo --model BAAI/bge-base-en-v1.5 --chunk-size 1000 --chunk-overlap 200
```

---

## 12. NVIDIA GPU / CUDA Setup

To ensure PyTorch uses your NVIDIA GPU:
1. Verify NVIDIA drivers are installed on Windows (`nvidia-smi`).
2. Install the CUDA-enabled PyTorch build:
   ```powershell
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```
3. Test with:
   ```powershell
   python index_project.py --gpu-info
   ```

---

## 13. Supabase Setup Guide

1. Create a project at [supabase.com](https://supabase.com).
2. Go to the **SQL Editor** tab.
3. Paste and execute the contents of [supabase/schema.sql](file:///d:/project/chatbot/supabase/schema.sql).
4. Copy your **Project URL** and **Service Role Secret** from `Project Settings > API`.

---

## 14. Database Schema & Stored RPC Functions

### Tables
- `projects`: Contains repository metadata, `github_url`, `readme_hash`, `embedding_model`, `embedding_dimension`, `indexed_at`.
- `readme_chunks`: Contains `project_id` (FK cascade), `chunk_index`, `section_title`, `section_path`, `content`, `embedding` (VECTOR).

### Stored Function: `match_readme_chunks`
```sql
CREATE OR REPLACE FUNCTION match_readme_chunks (
    query_embedding VECTOR,
    match_project_id UUID,
    match_count INT DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    id UUID,
    project_id UUID,
    chunk_index INT,
    section_title TEXT,
    section_path TEXT,
    content TEXT,
    similarity FLOAT
)
...
```

---

## 15. Render Deployment Guide

### Option 1: Automatic Blueprint (Recommended)
1. Push this repository to GitHub.
2. Log in to [render.com](https://render.com) and click **New > Blueprint**.
3. Select this repository. Render will automatically read `render.yaml`.
4. Fill in the environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).

### Option 2: Manual Web Service
1. **Environment**: Python 3.11
2. **Build Command**: `pip install -r backend/requirements-render.txt`
3. **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Set required environment variables.

---

## 16. Environment Variables Reference

### Backend (`backend/.env`)
| Variable | Default | Description |
|---|---|---|
| `SUPABASE_URL` | *(Required)* | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | *(Required)* | Supabase service key |
| `MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Question embedding model |
| `GENERATOR_MODEL` | `google/flan-t5-small` | Seq2Seq answer generator |
| `TOP_K` | `5` | Max chunks retrieved |
| `SIMILARITY_THRESHOLD` | `0.40` | Min cosine score for retrieval |
| `MAX_NEW_TOKENS` | `128` | Max generation tokens |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

---

## 17. Frontend Integration Guide

The frontend is a vanilla JavaScript widget with glassmorphism styling and zero framework dependencies.

### Embedding into Any Website
Add the stylesheet, container, and script to your HTML page:

```html
<!-- In <head> -->
<link rel="stylesheet" href="https://your-domain.com/style.css">

<!-- Before </body> -->
<div id="readme-chatbot-root"></div>
<script src="https://your-domain.com/app.js"></script>
<script>
    const bot = initializeChatbot({
        projectId: "YOUR-SUPABASE-PROJECT-UUID",
        apiUrl: "https://your-backend-app.onrender.com",
        theme: "dark",
        autoOpen: false
    });
</script>
```

---

## 18. Re-indexing & Multi-Project Isolation

- Multiple repositories can be indexed in the same Supabase database.
- When chatting with Project A, the backend calls `match_readme_chunks` strictly specifying `match_project_id = Project_A_UUID`.
- Vectors from Project B are **never** queried or returned.

---

## 19. README Hash & Change Detection

- Whenever `index_project.py` runs, it fetches the repository README and computes `hashlib.sha256(content.encode('utf-8')).hexdigest()`.
- It compares this hash with the stored `readme_hash` in Supabase.
- If identical:
  ```
  README has not changed. No re-indexing required.
  ```
- If different (or `--force` is specified):
  1. Old chunks for the project are deleted (`DELETE FROM readme_chunks WHERE project_id = ...`).
  2. New chunks and embeddings are generated using the GPU.
  3. New records and updated hash are stored.

---

## 20. Performance & Low-Memory Optimization

- **Render RAM Footprint**: ~350MB total.
- **Fast Startup**: Models are pre-warmed once during server startup using FastAPI lifespan hooks.
- **torch.no_grad()**: All inference steps disable gradient calculation, saving CPU memory and execution time.

---

## 21. Security Best Practices

- ✅ **GitHub URL Sanitization**: Regex validation prevents malicious URLs.
- ✅ **Size Limits**: README downloads are capped at 2MB to prevent memory exhaustion.
- ✅ **No Remote Code Execution**: No git cloning or shell execution.
- ✅ **Backend Mediated**: Frontend never accesses Supabase service keys.
- ✅ **Input Validation**: Questions are capped at 500 characters and validated using Pydantic.

---

## 22. Limitations

- Only processes the `README.md` (or top-level documentation file). Code files and issues are not indexed.
- Small models (`FLAN-T5-small`) are designed for concise extractive and summary answers. Very complex multi-step reasoning may require configuring larger models (e.g. `flan-t5-base`).

---

## 23. Future Improvements & Model Upgrades

- [ ] Support multi-file Markdown documentation directories (e.g. `docs/`).
- [ ] Upgrade option to `google/flan-t5-base` or `google/flan-t5-large`.
- [ ] User feedback tracking (thumbs up/down) in Supabase.
- [ ] Streaming response support via Server-Sent Events (SSE).
