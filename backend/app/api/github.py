from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

router = APIRouter(prefix="/github", tags=["GitHub"])


class SyncRequest(BaseModel):
    repo_url: Optional[str] = Field(None, description="GitHub repository URL to sync")
    branch: Optional[str] = Field(None, description="Branch to fetch README from (default: repo default)")
    token: Optional[str] = Field(None, description="Optional GitHub Personal Access Token")
    force: bool = Field(False, description="Force re-indexing even if SHA is unchanged")


@router.get("/status")
async def get_github_status(request: Request) -> Dict[str, Any]:
    """Returns the current GitHub README synchronization status."""
    sync_manager = getattr(request.app.state, "sync_manager", None)
    if not sync_manager:
        raise HTTPException(status_code=500, detail="Sync manager not initialized.")
    return sync_manager.get_status()


@router.post("/sync")
async def sync_github_readme(payload: SyncRequest, request: Request) -> Dict[str, Any]:
    """Manually triggers GitHub README synchronization and vector store indexing."""
    sync_manager = getattr(request.app.state, "sync_manager", None)
    settings = getattr(request.app.state, "settings", None)

    if not sync_manager or not settings:
        raise HTTPException(status_code=500, detail="Services not initialized.")

    target_repo = payload.repo_url or settings.GITHUB_REPO_URL
    target_branch = payload.branch if payload.branch is not None else settings.GITHUB_BRANCH
    target_token = payload.token if payload.token is not None else settings.GITHUB_TOKEN

    result = await sync_manager.sync(
        repo_url=target_repo,
        branch=target_branch,
        token=target_token,
        force=payload.force,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result
