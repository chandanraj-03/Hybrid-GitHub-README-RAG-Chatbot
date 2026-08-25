from backend.app.api.health import router as health_router
from backend.app.api.github import router as github_router
from backend.app.api.chat import router as chat_router

__all__ = ["health_router", "github_router", "chat_router"]
