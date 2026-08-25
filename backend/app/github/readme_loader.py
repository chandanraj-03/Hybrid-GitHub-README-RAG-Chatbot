import base64
from dataclasses import dataclass
from typing import Optional
from backend.app.github.client import GitHubClient, GitHubClientError


@dataclass
class ReadmeDocument:
    owner: str
    repo: str
    branch: str
    sha: str
    filename: str
    raw_markdown: str
    html_url: Optional[str] = None
    size: int = 0


class GitHubReadmeLoader:
    """Loads and decodes README files from GitHub repositories."""

    def __init__(self, client: Optional[GitHubClient] = None, token: Optional[str] = None):
        self.client = client or GitHubClient(token=token)

    async def fetch_readme(
        self,
        repo_url: str,
        branch: Optional[str] = None,
    ) -> ReadmeDocument:
        """
        Fetches, decodes, and constructs a ReadmeDocument from a GitHub repository.
        """
        owner, repo = self.client.parse_repo_url(repo_url)

        # If branch is not specified, query repository metadata for default branch
        target_branch = branch.strip() if branch and branch.strip() else None
        if not target_branch:
            repo_info = await self.client.get_repo_info(owner, repo)
            target_branch = repo_info.get("default_branch", "main")

        readme_data = await self.client.get_readme_data(owner, repo, branch=target_branch)

        # Decode base64 content
        encoding = readme_data.get("encoding", "base64")
        content_raw = readme_data.get("content", "")

        if encoding == "base64":
            try:
                decoded_bytes = base64.b64decode(content_raw)
                raw_markdown = decoded_bytes.decode("utf-8", errors="replace")
            except Exception as e:
                raise GitHubClientError(f"Failed to decode base64 README content: {e}")
        else:
            raw_markdown = content_raw

        return ReadmeDocument(
            owner=owner,
            repo=repo,
            branch=target_branch,
            sha=readme_data.get("sha", ""),
            filename=readme_data.get("name", "README.md"),
            raw_markdown=raw_markdown,
            html_url=readme_data.get("html_url"),
            size=readme_data.get("size", len(raw_markdown)),
        )
