import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from laptop.app.config import laptop_settings
from laptop.app.auth import verify_bearer_token
from laptop.app.model import LaptopTransformerModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Laptop-LLM] %(name)s: %(message)s",
)
logger = logging.getLogger("laptop_main")

model_engine = LaptopTransformerModel()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Laptop LLM Service...")
    # Pre-load or warm up model asynchronously
    asyncio.create_task(asyncio.to_thread(model_engine.load_model))
    yield
    logger.info("Shutting down Laptop LLM Service...")


app = FastAPI(
    title="Laptop Local LLM Service",
    version="1.0.0",
    description="Local transformer inference server for Hybrid GitHub README RAG.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContextItem(BaseModel):
    text: str
    section: Optional[str] = "Overview"


class GenerateRequest(BaseModel):
    question: str = Field(..., description="User question")
    context: List[ContextItem] = Field(default_factory=list, description="Retrieved README context chunks")
    conversation: Optional[List[Dict[str, str]]] = Field(default=None, description="Previous chat conversation")


class GenerateResponse(BaseModel):
    answer: str
    model: str


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint to probe local model availability."""
    return {
        "status": "ok",
        "model": laptop_settings.LOCAL_MODEL_NAME,
        "device": laptop_settings.DEVICE,
    }


@app.post("/generate", response_model=GenerateResponse, dependencies=[Depends(verify_bearer_token)])
async def generate_endpoint(payload: GenerateRequest) -> GenerateResponse:
    """Generates grounded answer using local transformer model."""
    context_dicts = [{"text": c.text, "section": c.section} for c in payload.context]

    answer = await asyncio.to_thread(
        model_engine.generate_answer,
        question=payload.question,
        context_chunks=context_dicts,
        conversation=payload.conversation,
    )

    return GenerateResponse(
        answer=answer,
        model=laptop_settings.LOCAL_MODEL_NAME,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "laptop.app.main:app",
        host="0.0.0.0",
        port=laptop_settings.PORT,
        reload=False,
    )
