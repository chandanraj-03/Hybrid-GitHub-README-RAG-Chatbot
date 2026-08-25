# Hybrid GitHub README RAG Chatbot

An intelligent RAG chatbot system whose sole knowledge base is a **GitHub repository's `README.md`**. It features a hybrid inference engine with **Local Laptop Transformer Model** priority and automatic failover to **Google Gemini**.

---

## Architecture Overview

```text
                     USER
                       │
                       ▼
               ┌───────────────┐
               │   Frontend    │  (Glassmorphic Dark Mode UI)
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ Render Backend│  (FastAPI + Vector Store)
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ GitHub README │  (Heading-aware Chunking + Embeddings)
               │      RAG      │
               └───────┬───────┘
                       │
                 Retrieved context
                       │
                       ▼
               ┌───────────────┐
               │ Try Local LLM │  (Bearer Auth + 4s Timeout)
               └───────┬───────┘
                       │
                ┌──────┴────────────┐
                │                   │
             ONLINE              OFFLINE / TIMEOUT / ERROR
                │                   │
                ▼                   ▼
       Laptop LLM (Transformers)   Gemini API (Fallback)
                │                   │
                └────────┬──────────┘
                         ▼   
                      Answer
                         │
                         ▼
             Structured Sources:
             README.md → Installation
             README.md → Usage
```

---

## Key Features

1. **GitHub README Grounding**:
   - Fetches README directly via official GitHub REST API (public repos or private repos with Personal Access Token).
   - Heading-aware Markdown chunking (`#`, `##`, `###`) preserving section hierarchy, bullet points, and code blocks.
   - SHA-based synchronization: Skips re-indexing when README SHA is unchanged; automatically re-embeds when changed.

2. **Laptop-First Priority with Automatic Failover**:
   - The local laptop model is always preferred.
   - If the laptop is offline, times out (default: 4s), returns HTTP 500, or sends an invalid response, it instantly and seamlessly falls back to Google Gemini.

3. **Cloudflare Quick Tunnel Ready**:
   - Zero-cost public exposure for your laptop without purchasing domains:
     ```bash
     cloudflared tunnel --url http://localhost:8000
     ```
   - Bearer token authentication prevents unauthorized access to the local LLM endpoint.

4. **Strict Grounding Constraints**:
   - Answers **ONLY** from the supplied README context.
   - If information is not in the README, responds with:
     > *"I couldn't find that information in the repository README."*
   - Never hallucinate databases or unsupported features.

5. **Source Citations**:
   - Every answer exposes structured citations:
     ```json
     {
       "answer": "Run pip install myproject.",
       "provider": "local",
       "sources": [
         { "file": "README.md", "section": "Installation" }
       ]
     }
     ```

---

## Project Structure

```text
hybrid-github-rag/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI server & CORS
│   │   ├── config.py                  # Pydantic Settings
│   │   ├── api/
│   │   │   ├── chat.py                # POST /api/chat
│   │   │   ├── github.py              # POST /api/github/sync, GET /api/github/status
│   │   │   └── health.py              # GET /api/health, GET /api/laptop-status
│   │   ├── github/
│   │   │   ├── client.py              # GitHub REST API client
│   │   │   ├── readme_loader.py       # Fetch README & decode base64
│   │   │   └── sync.py                # SHA tracking & selective sync
│   │   ├── rag/
│   │   │   ├── chunker.py             # Heading-aware Markdown chunker
│   │   │   ├── embeddings.py          # Sentence-transformers / fallback embeddings
│   │   │   ├── vector_store.py        # In-memory cosine similarity vector store
│   │   │   ├── retriever.py           # Top-K chunk retrieval & source extraction
│   │   │   └── pipeline.py            # End-to-end RAG indexing & query pipeline
│   │   ├── providers/
│   │   │   ├── base.py                # BaseLLMProvider & Grounding Prompt
│   │   │   ├── local.py               # Laptop LLM client with timeout & auth
│   │   │   └── gemini.py              # Google Gemini API provider
│   │   └── services/
│   │       ├── laptop_health.py       # Latency & availability checker
│   │       └── orchestrator.py        # Priority & failover orchestrator
│   ├── tests/                         # Comprehensive pytest test suite
│   ├── requirements.txt
│   └── .env.example
│
├── laptop/
│   ├── app/
│   │   ├── main.py                    # FastAPI app for local model (Port 8000)
│   │   ├── config.py                  # Model & Bearer auth config
│   │   ├── auth.py                    # Bearer token validation
│   │   └── model.py                   # Transformers pipeline (Qwen/TinyLlama)
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html                     # Glassmorphic single-page app
│   ├── style.css                      # Modern dark theme stylesheet
│   └── app.js                         # Chat UI, failover badge, source citations
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Quickstart Guide

### 1. Start the Local Laptop LLM Service

```bash
# In terminal 1 (Laptop)
cd laptop
pip install -r requirements.txt
python -m uvicorn laptop.app.main:app --host 0.0.0.0 --port 8000
```

*(Optional) Expose laptop via Cloudflare Quick Tunnel:*
```bash
cloudflared tunnel --url http://localhost:8000
```

### 2. Start the Backend API

```bash
# In terminal 2 (Backend)
cd backend
pip install -r requirements.txt

# Configure environment in .env
cp .env.example .env
# Set GEMINI_API_KEY, GITHUB_REPO_URL, and LAPTOP_API_URL

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 3. Open the Frontend

Open `frontend/index.html` in your browser or run:
```bash
# In terminal 3 (Frontend)
cd frontend
python -m http.server 3000
```
Navigate to `http://localhost:3000`.

---

## API Reference

### Health & Status
- `GET /api/health`: Health status and number of indexed README chunks.
- `GET /api/laptop-status`: Status, latency, and model info of the local laptop LLM.
- `GET /api/github/status`: Current repository, branch, SHA, and sync state.

### README Synchronization
- `POST /api/github/sync`:
  ```json
  {
    "repo_url": "https://github.com/owner/repository",
    "branch": "main",
    "token": null,
    "force": false
  }
  ```

### Chat Inference
- `POST /api/chat`:
  ```json
  {
    "message": "How do I install this project?",
    "conversation": []
  }
  ```
  Response:
  ```json
  {
    "answer": "Run pip install myproject",
    "provider": "local",
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "sources": [
      {
        "file": "README.md",
        "section": "Installation"
      }
    ],
    "failover": false,
    "failover_reason": null,
    "retrieved_chunks_count": 2
  }
  ```

---

## Running Automated Tests

Run the full pytest suite:

```bash
python -m pytest backend/tests laptop/tests -v
```
