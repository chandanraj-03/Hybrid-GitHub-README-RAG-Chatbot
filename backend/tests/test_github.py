import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.github.client import GitHubClient, GitHubClientError
from backend.app.github.readme_loader import GitHubReadmeLoader, ReadmeDocument
from backend.app.github.sync import GitHubSyncManager


class TestGitHubClient:

    def test_parse_repo_url_variations(self):
        client = GitHubClient()

        # HTTPS standard
        owner, repo = client.parse_repo_url("https://github.com/owner/my-repo")
        assert owner == "owner" and repo == "my-repo"

        # HTTPS with .git
        owner, repo = client.parse_repo_url("https://github.com/owner/my-repo.git")
        assert owner == "owner" and repo == "my-repo"

        # Short form
        owner, repo = client.parse_repo_url("owner/my-repo")
        assert owner == "owner" and repo == "my-repo"

        # SSH style
        owner, repo = client.parse_repo_url("git@github.com:owner/my-repo.git")
        assert owner == "owner" and repo == "my-repo"

    def test_parse_invalid_repo_url(self):
        client = GitHubClient()
        with pytest.raises(GitHubClientError):
            client.parse_repo_url("invalid-url-without-slash")

        with pytest.raises(GitHubClientError):
            client.parse_repo_url("")

    def test_auth_headers_with_and_without_token(self):
        # Without token
        c1 = GitHubClient(token=None)
        h1 = c1._get_headers()
        assert "Authorization" not in h1
        assert h1["User-Agent"] == "GitHub-README-RAG-Chatbot"

        # With token
        c2 = GitHubClient(token="ghp_test123456789")
        h2 = c2._get_headers()
        assert h2["Authorization"] == "Bearer ghp_test123456789"


@pytest.mark.asyncio
class TestReadmeLoader:

    async def test_fetch_readme_decodes_base64(self, sample_readme_text):
        raw_encoded = base64.b64encode(sample_readme_text.encode("utf-8")).decode("utf-8")

        mock_client = MagicMock(spec=GitHubClient)
        mock_client.parse_repo_url.return_value = ("test-owner", "test-repo")
        mock_client.get_readme_data = AsyncMock(return_value={
            "name": "README.md",
            "sha": "abc123sha",
            "encoding": "base64",
            "content": raw_encoded,
            "html_url": "https://github.com/test-owner/test-repo/blob/main/README.md",
            "size": len(sample_readme_text),
        })

        loader = GitHubReadmeLoader(client=mock_client)
        doc = await loader.fetch_readme("https://github.com/test-owner/test-repo", branch="main")

        assert doc.owner == "test-owner"
        assert doc.repo == "test-repo"
        assert doc.branch == "main"
        assert doc.sha == "abc123sha"
        assert "pip install test-project" in doc.raw_markdown

    async def test_fetch_readme_auto_detects_default_branch(self):
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.parse_repo_url.return_value = ("test-owner", "test-repo")
        mock_client.get_repo_info = AsyncMock(return_value={"default_branch": "master"})
        mock_client.get_readme_data = AsyncMock(return_value={
            "name": "README.md",
            "sha": "def456sha",
            "encoding": "utf-8",
            "content": "# Master branch readme",
        })

        loader = GitHubReadmeLoader(client=mock_client)
        doc = await loader.fetch_readme("https://github.com/test-owner/test-repo", branch=None)

        assert doc.branch == "master"
        mock_client.get_repo_info.assert_called_once_with("test-owner", "test-repo")


@pytest.mark.asyncio
class TestGitHubSyncManager:

    async def test_sync_initial_and_sha_change(self, sample_readme_text):
        mock_loader = MagicMock(spec=GitHubReadmeLoader)
        mock_loader.client = MagicMock()
        mock_loader.fetch_readme = AsyncMock(return_value=ReadmeDocument(
            owner="owner",
            repo="repo",
            branch="main",
            sha="sha_v1",
            filename="README.md",
            raw_markdown=sample_readme_text,
        ))

        mock_rag = MagicMock()
        mock_rag.index_readme = AsyncMock(return_value=3)

        sync_mgr = GitHubSyncManager(loader=mock_loader, rag_pipeline=mock_rag)

        # First sync -> re-indexes
        res1 = await sync_mgr.sync("https://github.com/owner/repo")
        assert res1["success"] is True
        assert res1["changed"] is True
        assert sync_mgr.current_sha == "sha_v1"
        assert sync_mgr.chunk_count == 3
        mock_rag.index_readme.assert_called_once()

        # Second sync with same SHA -> skips re-indexing
        mock_rag.index_readme.reset_mock()
        res2 = await sync_mgr.sync("https://github.com/owner/repo")
        assert res2["success"] is True
        assert res2["changed"] is False
        mock_rag.index_readme.assert_not_called()

        # Third sync with changed SHA -> re-indexes
        mock_loader.fetch_readme = AsyncMock(return_value=ReadmeDocument(
            owner="owner",
            repo="repo",
            branch="main",
            sha="sha_v2",
            filename="README.md",
            raw_markdown=sample_readme_text + "\n## New Section\nContent",
        ))
        res3 = await sync_mgr.sync("https://github.com/owner/repo")
        assert res3["success"] is True
        assert res3["changed"] is True
        assert sync_mgr.current_sha == "sha_v2"
        mock_rag.index_readme.assert_called_once()
