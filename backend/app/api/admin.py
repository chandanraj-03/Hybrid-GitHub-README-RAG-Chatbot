import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, HTTPException, Depends, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.app.providers.base import BaseLLMProvider
from backend.app.providers.local import LocalLaptopProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.providers.grok import GrokProvider
from backend.app.providers.groq import GroqProvider
from backend.app.providers.openrouter import OpenRouterProvider

logger = logging.getLogger("admin_api")
router = APIRouter(prefix="/admin", tags=["Admin Live Sync"])

security_scheme = HTTPBearer(auto_error=False)


def verify_admin_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> bool:
    """Verifies that the caller possesses the LAPTOP_API_TOKEN."""
    settings = getattr(request.app.state, "settings", None)
    expected_token = settings.LAPTOP_API_TOKEN if settings else "secret-laptop-token"

    if not expected_token:
        return True

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


class UpdateConfigRequest(BaseModel):
    laptop_api_url: Optional[str] = Field(default=None, description="New Cloudflare tunnel or laptop URL")
    gemini_api_key: Optional[str] = Field(default=None, description="Google Gemini API key")
    groq_api_key: Optional[str] = Field(default=None, description="Groq Cloud API key")
    grok_api_key: Optional[str] = Field(default=None, description="xAI Grok API key")
    openrouter_api_key: Optional[str] = Field(default=None, description="OpenRouter API key")
    github_repo_url: Optional[str] = Field(default=None, description="GitHub repository URL")
    local_llm_timeout: Optional[float] = Field(default=None, description="Timeout in seconds for local model")
    fallback_cascade_order: Optional[str] = Field(default=None, description="Provider cascade order")


class RegisterTunnelRequest(BaseModel):
    tunnel_url: str = Field(..., description="Active Cloudflare quick tunnel HTTPS URL")


def rebuild_provider_cascade(app):
    """Rebuilds the active provider list inside orchestrator from updated providers."""
    settings = app.state.settings
    provider_map = {
        "local": app.state.local_provider,
        "gemini": app.state.gemini_provider,
        "groq": app.state.groq_provider,
        "grok": app.state.grok_provider,
        "openrouter": app.state.openrouter_provider,
    }
    cascade_names = [name.strip().lower() for name in settings.FALLBACK_CASCADE_ORDER.split(",") if name.strip()]
    ordered_providers: List[BaseLLMProvider] = [
        provider_map[name] for name in cascade_names if name in provider_map
    ]
    app.state.orchestrator.providers = ordered_providers
    logger.info(f"Rebuilt provider cascade: {[p.name for p in ordered_providers]}")


@router.post("/register-tunnel", dependencies=[Depends(verify_admin_token)])
async def register_tunnel(payload: RegisterTunnelRequest, request: Request) -> Dict[str, Any]:
    """
    Registers a new live Cloudflare Tunnel URL from the laptop without server restart.
    """
    clean_url = payload.tunnel_url.strip().rstrip("/")
    if not clean_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid tunnel URL format.")

    request.app.state.settings.LAPTOP_API_URL = clean_url
    request.app.state.local_provider.base_url = clean_url

    logger.info(f"Registered new laptop tunnel URL: {clean_url}")
    return {
        "status": "success",
        "message": f"Laptop tunnel registered successfully: {clean_url}",
        "laptop_api_url": clean_url,
    }


@router.post("/config", dependencies=[Depends(verify_admin_token)])
async def update_runtime_config(payload: UpdateConfigRequest, request: Request) -> Dict[str, Any]:
    """
    Dynamically updates API keys, repository, or settings on Render in-memory in real time.
    """
    settings = request.app.state.settings
    updated_fields = []

    if payload.laptop_api_url is not None:
        clean_url = payload.laptop_api_url.strip().rstrip("/")
        settings.LAPTOP_API_URL = clean_url
        request.app.state.local_provider.base_url = clean_url
        updated_fields.append("laptop_api_url")

    if payload.local_llm_timeout is not None:
        settings.LOCAL_LLM_TIMEOUT = payload.local_llm_timeout
        request.app.state.local_provider.timeout = payload.local_llm_timeout
        updated_fields.append("local_llm_timeout")

    if payload.gemini_api_key is not None:
        key = payload.gemini_api_key.strip()
        settings.GEMINI_API_KEY = key if key else None
        request.app.state.gemini_provider.api_key = key if key else None
        updated_fields.append("gemini_api_key")

    if payload.groq_api_key is not None:
        key = payload.groq_api_key.strip()
        settings.GROQ_API_KEY = key if key else None
        request.app.state.groq_provider.api_key = key if key else None
        updated_fields.append("groq_api_key")

    if payload.grok_api_key is not None:
        key = payload.grok_api_key.strip()
        settings.GROK_API_KEY = key if key else None
        request.app.state.grok_provider.api_key = key if key else None
        updated_fields.append("grok_api_key")

    if payload.openrouter_api_key is not None:
        key = payload.openrouter_api_key.strip()
        settings.OPENROUTER_API_KEY = key if key else None
        request.app.state.openrouter_provider.api_key = key if key else None
        updated_fields.append("openrouter_api_key")

    if payload.fallback_cascade_order is not None:
        settings.FALLBACK_CASCADE_ORDER = payload.fallback_cascade_order.strip()
        updated_fields.append("fallback_cascade_order")

    # Rebuild orchestrator cascade
    rebuild_provider_cascade(request.app)

    # If repo URL changed, trigger sync
    if payload.github_repo_url is not None and payload.github_repo_url != settings.GITHUB_REPO_URL:
        new_repo = payload.github_repo_url.strip()
        settings.GITHUB_REPO_URL = new_repo
        updated_fields.append("github_repo_url")
        try:
            sync_res = await request.app.state.sync_manager.sync(
                repo_url=new_repo,
                force=True,
            )
            logger.info(f"Triggered re-sync for new repo '{new_repo}': {sync_res.get('message')}")
        except Exception as exc:
            logger.error(f"Failed to auto-sync new repository '{new_repo}': {exc}")

    return {
        "status": "success",
        "message": f"Successfully updated runtime configuration for: {', '.join(updated_fields)}",
        "updated_fields": updated_fields,
    }


@router.get("/config", dependencies=[Depends(verify_admin_token)])
async def get_runtime_config(request: Request) -> Dict[str, Any]:
    """Returns the current masked runtime configuration."""
    settings = request.app.state.settings
    return {
        "github_repo_url": settings.GITHUB_REPO_URL,
        "laptop_api_url": settings.LAPTOP_API_URL,
        "local_llm_timeout": settings.LOCAL_LLM_TIMEOUT,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "grok_configured": bool(settings.GROK_API_KEY),
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "fallback_cascade_order": settings.FALLBACK_CASCADE_ORDER,
        "indexed_chunks": request.app.state.sync_manager.chunk_count,
    }
