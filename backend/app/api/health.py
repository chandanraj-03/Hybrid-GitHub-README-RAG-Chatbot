from fastapi import APIRouter, Request
from typing import Dict, Any

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Returns general backend health and RAG index statistics."""
    rag_pipeline = getattr(request.app.state, "rag_pipeline", None)
    chunk_count = rag_pipeline.count() if rag_pipeline else 0

    return {
        "status": "healthy",
        "app": request.app.title,
        "version": request.app.version,
        "indexed_chunks": chunk_count,
    }


@router.get("/laptop-status")
async def laptop_status(request: Request) -> Dict[str, Any]:
    """Returns connectivity and latency status of the local laptop LLM."""
    laptop_health_svc = getattr(request.app.state, "laptop_health", None)
    if not laptop_health_svc:
        return {"online": False, "error": "Laptop health service not initialized."}

    return await laptop_health_svc.get_status()
