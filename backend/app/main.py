import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.github.client import GitHubClient
from backend.app.github.readme_loader import GitHubReadmeLoader
from backend.app.github.sync import GitHubSyncManager
from backend.app.rag.chunker import MarkdownHeadingChunker
from backend.app.rag.embeddings import get_embedding_model
from backend.app.rag.vector_store import InMemoryVectorStore
from backend.app.rag.pipeline import RagPipeline
from backend.app.providers.base import BaseLLMProvider
from backend.app.providers.local import LocalLaptopProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.providers.grok import GrokProvider
from backend.app.providers.groq import GroqProvider
from backend.app.providers.openrouter import OpenRouterProvider
from backend.app.services.laptop_health import LaptopHealthService
from backend.app.services.orchestrator import RagOrchestrator
from backend.app.api.health import router as health_router
from backend.app.api.github import router as github_router
from backend.app.api.chat import router as chat_router
from backend.app.api.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backend_main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes RAG, GitHub sync, and multi-provider LLM cascade on startup."""
    logger.info("Initializing Hybrid GitHub README RAG Backend with Multi-Provider Cascade...")

    # 1. RAG Core
    chunker = MarkdownHeadingChunker(max_chunk_size=800, chunk_overlap=100)
    embedding_model = get_embedding_model(settings.EMBEDDING_PROVIDER)
    vector_store = InMemoryVectorStore()
    rag_pipeline = RagPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        vector_store=vector_store,
    )

    # 2. GitHub Components
    github_client = GitHubClient(token=settings.GITHUB_TOKEN)
    readme_loader = GitHubReadmeLoader(client=github_client)
    sync_manager = GitHubSyncManager(loader=readme_loader, rag_pipeline=rag_pipeline)

    # 3. LLM Providers Cascade
    local_provider = LocalLaptopProvider(
        base_url=settings.LAPTOP_API_URL or "http://localhost:16036",
        auth_token=settings.LAPTOP_API_TOKEN,
        timeout=settings.LOCAL_LLM_TIMEOUT,
    )
    gemini_provider = GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        top_p=settings.LLM_TOP_P,
    )
    grok_provider = GrokProvider(
        api_key=settings.GROK_API_KEY,
        model=settings.GROK_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        top_p=settings.LLM_TOP_P,
        presence_penalty=settings.LLM_PRESENCE_PENALTY,
        frequency_penalty=settings.LLM_FREQUENCY_PENALTY,
    )
    groq_provider = GroqProvider(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        top_p=settings.LLM_TOP_P,
        presence_penalty=settings.LLM_PRESENCE_PENALTY,
        frequency_penalty=settings.LLM_FREQUENCY_PENALTY,
    )
    openrouter_provider = OpenRouterProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        top_p=settings.LLM_TOP_P,
        presence_penalty=settings.LLM_PRESENCE_PENALTY,
        frequency_penalty=settings.LLM_FREQUENCY_PENALTY,
    )

    # Map provider names to instances
    provider_map = {
        "local": local_provider,
        "gemini": gemini_provider,
        "groq": groq_provider,
        "grok": grok_provider,
        "openrouter": openrouter_provider,
    }

    # Construct ordered cascade list based on settings
    cascade_names = [name.strip().lower() for name in settings.FALLBACK_CASCADE_ORDER.split(",") if name.strip()]
    ordered_providers: List[BaseLLMProvider] = [
        provider_map[name] for name in cascade_names if name in provider_map
    ]

    # 4. Services
    laptop_health = LaptopHealthService(local_provider=local_provider)
    orchestrator = RagOrchestrator(
        rag_pipeline=rag_pipeline,
        providers=ordered_providers,
        top_k=settings.TOP_K_CHUNKS,
    )

    # Attach to app.state
    app.state.settings = settings
    app.state.rag_pipeline = rag_pipeline
    app.state.github_client = github_client
    app.state.readme_loader = readme_loader
    app.state.sync_manager = sync_manager
    app.state.local_provider = local_provider
    app.state.gemini_provider = gemini_provider
    app.state.groq_provider = groq_provider
    app.state.grok_provider = grok_provider
    app.state.openrouter_provider = openrouter_provider
    app.state.laptop_health = laptop_health
    app.state.orchestrator = orchestrator

    # Background initial README sync
    if settings.GITHUB_REPO_URL:
        async def initial_sync():
            try:
                logger.info(f"Starting initial README sync for '{settings.GITHUB_REPO_URL}'...")
                res = await sync_manager.sync(
                    repo_url=settings.GITHUB_REPO_URL,
                    branch=settings.GITHUB_BRANCH,
                    token=settings.GITHUB_TOKEN,
                )
                logger.info(f"Initial sync result: {res.get('message')}")
            except Exception as e:
                logger.error(f"Initial README sync failed: {e}")

        asyncio.create_task(initial_sync())

    yield
    logger.info("Shutting down Hybrid GitHub README RAG Backend...")


app = FastAPI(
    title="Hybrid GitHub README RAG Chatbot API",
    version=settings.APP_VERSION,
    description="RAG Chatbot grounded in GitHub repository READMEs with Multi-Provider Cascading Failover.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(github_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "Welcome to Hybrid GitHub README RAG API with Multi-Provider Cascade",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "chat_url": "/api/chat",
        "github_sync_url": "/api/github/sync",
        "github_status_url": "/api/github/status",
        "cascade_order": settings.FALLBACK_CASCADE_ORDER,
    }
