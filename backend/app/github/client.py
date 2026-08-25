import re
from typing import Dict, Any, Optional, Tuple
import httpx


class GitHubClientError(Exception):
    """Custom exception for GitHub API client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    """GitHub REST API client for repository inspection and content retrieval."""

    def __init__(self, token: Optional[str] = None):
        self.token = token.strip() if token and token.strip() else None
        self.base_url = "https://api.github.com"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitHub-README-RAG-Chatbot",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def parse_repo_url(repo_url: str) -> Tuple[str, str]:
        """
        Parses owner and repo name from GitHub URL or 'owner/repo' format.
        Examples:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git
        - owner/repo
        """
        if not repo_url or not isinstance(repo_url, str):
            raise GitHubClientError("GitHub repository URL is required.")

        cleaned = repo_url.strip()
        cleaned = re.sub(r"\.git$", "", cleaned)

        # Match HTTPS / HTTP / SSH / standard owner/repo
        patterns = [
            r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
            r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                owner, repo = match.group(1), match.group(2)
                return owner, repo

        raise GitHubClientError(f"Invalid GitHub repository URL or format: '{repo_url}'")

    async def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches repository metadata, including default branch."""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
            except httpx.RequestError as exc:
                raise GitHubClientError(f"Network error connecting to GitHub: {exc}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise GitHubClientError(f"Repository '{owner}/{repo}' not found on GitHub.", status_code=404)
            elif response.status_code in (401, 403):
                raise GitHubClientError(
                    f"Authentication or rate limit error accessing '{owner}/{repo}' (HTTP {response.status_code}).",
                    status_code=response.status_code,
                )
            else:
                raise GitHubClientError(
                    f"Failed to fetch repository metadata: HTTP {response.status_code} - {response.text}",
                    status_code=response.status_code,
                )

    async def get_readme_data(self, owner: str, repo: str, branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches the README file metadata and content for a repository.
        If branch is provided, queries for that specific ref.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/readme"
        params = {}
        if branch and branch.strip():
            params["ref"] = branch.strip()

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=self._get_headers(), params=params)
            except httpx.RequestError as exc:
                raise GitHubClientError(f"Network error fetching README from GitHub: {exc}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                branch_msg = f" on branch '{branch}'" if branch else ""
                raise GitHubClientError(f"README.md not found for repository '{owner}/{repo}'{branch_msg}.", status_code=404)
            elif response.status_code in (401, 403):
                raise GitHubClientError(
                    f"Authentication or rate limit error accessing README for '{owner}/{repo}' (HTTP {response.status_code}).",
                    status_code=response.status_code,
                )
            else:
                raise GitHubClientError(
                    f"Failed to fetch README: HTTP {response.status_code} - {response.text}",
                    status_code=response.status_code,
                )
