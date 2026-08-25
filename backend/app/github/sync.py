import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from backend.app.github.readme_loader import GitHubReadmeLoader, ReadmeDocument
from backend.app.github.client import GitHubClientError


class GitHubSyncManager:
    """Manages GitHub README synchronization and change detection."""

    def __init__(self, loader: Optional[GitHubReadmeLoader] = None, rag_pipeline=None):
        self.loader = loader or GitHubReadmeLoader()
        self.rag_pipeline = rag_pipeline
        self.current_sha: Optional[str] = None
        self.current_repo: Optional[str] = None
        self.current_branch: Optional[str] = None
        self.current_filename: str = "README.md"
        self.status: str = "pending"
        self.last_synced_at: Optional[str] = None
        self.chunk_count: int = 0
        self.error_message: Optional[str] = None
        self._lock = asyncio.Lock()

    def set_rag_pipeline(self, pipeline):
        self.rag_pipeline = pipeline

    def get_status(self) -> Dict[str, Any]:
        """Returns the current synchronization status dictionary."""
        return {
            "repository": self.current_repo,
            "branch": self.current_branch,
            "file": self.current_filename,
            "sha": self.current_sha,
            "status": self.status,
            "last_synced_at": self.last_synced_at,
            "chunk_count": self.chunk_count,
            "error": self.error_message,
        }

    async def sync(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        token: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Synchronizes README for the given repo and branch.
        Skips re-indexing if SHA is unchanged, unless force=True.
        """
        async with self._lock:
            self.status = "syncing"
            self.error_message = None

            if token is not None:
                self.loader.client.token = token.strip() if token.strip() else None

            try:
                readme_doc: ReadmeDocument = await self.loader.fetch_readme(
                    repo_url=repo_url,
                    branch=branch,
                )

                repo_full_name = f"{readme_doc.owner}/{readme_doc.repo}"
                sha_changed = (readme_doc.sha != self.current_sha) or (repo_full_name != self.current_repo)

                if not sha_changed and not force and self.status != "pending" and self.chunk_count > 0:
                    self.status = "synced"
                    return {
                        "success": True,
                        "changed": False,
                        "message": "README is up-to-date. Using existing indexed embeddings.",
                        "data": self.get_status(),
                    }

                # Re-index with RAG pipeline if provided
                num_chunks = 0
                if self.rag_pipeline:
                    num_chunks = await self.rag_pipeline.index_readme(readme_doc)

                self.current_repo = repo_full_name
                self.current_branch = readme_doc.branch
                self.current_filename = readme_doc.filename
                self.current_sha = readme_doc.sha
                self.chunk_count = num_chunks
                self.status = "synced"
                self.last_synced_at = datetime.now(timezone.utc).isoformat()

                return {
                    "success": True,
                    "changed": True,
                    "message": f"Successfully synced and indexed {num_chunks} chunks from {readme_doc.filename}.",
                    "data": self.get_status(),
                }

            except (GitHubClientError, Exception) as exc:
                self.status = "error"
                self.error_message = str(exc)
                return {
                    "success": False,
                    "changed": False,
                    "message": f"Failed to sync README: {exc}",
                    "data": self.get_status(),
                }
