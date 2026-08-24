"""
FastAPI Main Application for Render Chatbot Backend.
Exposes /api/chat, /api/projects/{project_id}, and /api/health.
Loads open-source models once at startup with torch.no_grad() inference.
"""

from contextlib import asynccontextmanager
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import sys
from pathlib import Path

# Enable both standalone root execution (cd backend && uvicorn main:app) and package execution
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from backend.config import BackendConfig
    from backend.schemas import (
        ChatRequest,
        ChatResponse,
        ProjectResponse,
        HealthResponse,
        SourceItem,
    )
    from backend.embeddings import QuestionEmbedder
    from backend.generator import AnswerGenerator, FALLBACK_ANSWER
    from backend.retrieval import ReadmeRetriever
    from backend.supabase_client import SupabaseService
except ImportError:
    from config import BackendConfig
    from schemas import (
        ChatRequest,
        ChatResponse,
        ProjectResponse,
        HealthResponse,
        SourceItem,
    )
    from embeddings import QuestionEmbedder
    from generator import AnswerGenerator, FALLBACK_ANSWER
    from retrieval import ReadmeRetriever
    from supabase_client import SupabaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("readme_rag_api")

# Optimize PyTorch CPU threads & memory for low-resource cloud containers (Render Free Tier <512MB RAM)
try:
    import torch
    torch.set_num_threads(1)
    if hasattr(torch, "set_num_interop_threads"):
        torch.set_num_interop_threads(1)
except Exception:
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Pre-warms embedding and generator models once during server startup.
    Ensures zero runtime re-initialization overhead.
    """
    import gc
    logger.info("Initializing Render Chatbot Server...")
    logger.info(f"Loading Question Embedder ({BackendConfig.EMBEDDING_MODEL_NAME})...")
    try:
        QuestionEmbedder.get_instance()
        logger.info("Question Embedder loaded successfully.")
    except Exception as e:
        logger.warning(f"Could not pre-load Question Embedder during startup: {e}")

    gc.collect()

    logger.info(f"Loading Generator Model ({BackendConfig.GENERATOR_MODEL_NAME})...")
    try:
        AnswerGenerator.get_instance()
        logger.info("Generator Model loaded successfully.")
    except Exception as e:
        logger.warning(f"Could not pre-load Generator Model during startup: {e}")

    yield

    logger.info("Shutting down Render Chatbot Server...")


app = FastAPI(
    title="README RAG Chatbot API",
    description="Lightweight open-source RAG API for answering questions grounded strictly in GitHub README files.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for embeddable frontend widgets
app.add_middleware(
    CORSMiddleware,
    allow_origins=BackendConfig.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["Diagnostics"])
def health_check() -> HealthResponse:
    """Returns server health and loaded model diagnostics."""
    embedder = QuestionEmbedder.get_instance()
    generator = AnswerGenerator.get_instance()
    
    return HealthResponse(
        status="ok",
        device=str(generator.device),
        embedding_model=embedder.model_name,
        generator_model=generator.model_name,
    )


@app.get("/api/projects", response_model=list[ProjectResponse], tags=["Projects"])
def list_all_projects() -> list[ProjectResponse]:
    """Returns a list of all indexed projects stored in Supabase."""
    supabase_service = SupabaseService.get_instance()
    try:
        raw_projects = supabase_service.list_projects()
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return []

    result = []
    for p in raw_projects:
        chunk_count = supabase_service.get_chunk_count(p["id"])
        result.append(
            ProjectResponse(
                id=p["id"],
                github_url=p["github_url"],
                owner=p["owner"],
                repo_name=p["repo_name"],
                readme_hash=p.get("readme_hash"),
                readme_url=p.get("readme_url"),
                embedding_model=p["embedding_model"],
                embedding_dimension=p["embedding_dimension"],
                chunk_count=chunk_count,
                indexed_at=p.get("indexed_at"),
                created_at=p.get("created_at"),
            )
        )
    return result


@app.get("/api/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
def get_project_details(project_id: str) -> ProjectResponse:
    """Returns metadata, README hash, and chunk count for a specific project."""
    supabase_service = SupabaseService.get_instance()
    
    try:
        project_data = supabase_service.get_project_by_id(project_id)
    except Exception as e:
        logger.error(f"Database error fetching project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection error",
        )

    if not project_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )

    chunk_count = supabase_service.get_chunk_count(project_id)

    return ProjectResponse(
        id=project_data["id"],
        github_url=project_data["github_url"],
        owner=project_data["owner"],
        repo_name=project_data["repo_name"],
        readme_hash=project_data.get("readme_hash"),
        readme_url=project_data.get("readme_url"),
        embedding_model=project_data["embedding_model"],
        embedding_dimension=project_data["embedding_dimension"],
        chunk_count=chunk_count,
        indexed_at=project_data.get("indexed_at"),
        created_at=project_data.get("created_at"),
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
def chat_with_readme(request: ChatRequest) -> ChatResponse:
    """
    RAG chat endpoint:
    1. Embeds user question.
    2. Searches Supabase pgvector for isolated project chunks.
    3. Evaluates similarity scores against threshold.
    4. Generates grounded answer using FLAN-T5 or returns strict fallback.
    """
    logger.info(f"Received query for project '{request.project_id}': {request.question}")

    # 1. Embed question
    try:
        embedder = QuestionEmbedder.get_instance()
        question_vector = embedder.embed_question(request.question)
    except Exception as e:
        logger.error(f"Question embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding for query",
        )

    # 2. Vector search in Supabase
    try:
        supabase_service = SupabaseService.get_instance()
        retriever = ReadmeRetriever(supabase_service)
        sources, context = retriever.retrieve(
            project_id=request.project_id,
            question_embedding=question_vector,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Database search failed: {str(e)}",
        )

    # 3. Grounded Answer Generation & Hallucination Refusal
    if not sources or not context:
        logger.info(f"No chunks passed similarity threshold for question: {request.question}")
        return ChatResponse(
            answer=FALLBACK_ANSWER,
            sources=[],
            project_id=request.project_id,
            model_used=BackendConfig.GENERATOR_MODEL_NAME,
        )

    try:
        generator = AnswerGenerator.get_instance()
        answer = generator.generate_answer(request.question, context)
    except Exception as e:
        logger.error(f"Answer generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response",
        )

    return ChatResponse(
        answer=answer,
        sources=sources,
        project_id=request.project_id,
        model_used=BackendConfig.GENERATOR_MODEL_NAME,
    )


# Mount frontend UI directory for direct browser access at http://localhost:8000/
from fastapi.staticfiles import StaticFiles
from pathlib import Path

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
