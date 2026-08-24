"""
GitHub Reader module.
Validates GitHub URLs, fetches raw README content across default branches,
computes SHA-256 integrity hashes, and enforces security constraints.
"""

import hashlib
import re
from typing import Tuple, Optional
from urllib.parse import urlparse
import requests

from indexer.config import IndexerConfig


class GitHubURLError(ValueError):
    """Raised when an invalid GitHub URL is provided."""
    pass


class ReadmeFetchError(RuntimeError):
    """Raised when the README cannot be fetched from GitHub."""
    pass


class ReadmeTooLargeError(RuntimeError):
    """Raised when the README exceeds the maximum allowable size."""
    pass


class GitHubReader:
    # Supported branches to try for raw README retrieval
    COMMON_BRANCHES = ["main", "master", "develop", "trunk"]
    
    # Supported README filenames
    README_FILENAMES = [
        "README.md",
        "readme.md",
        "README.MD",
        "Readme.md",
        "README.markdown",
        "README.rst",
        "README.txt",
        "README",
    ]

    @staticmethod
    def parse_github_url(url: str) -> Tuple[str, str, str]:
        """
        Validates and parses a GitHub repository URL.
        
        Args:
            url: GitHub repository URL or shorthand (e.g. 'https://github.com/owner/repo')
            
        Returns:
            Tuple of (normalized_url, owner, repo_name)
            
        Raises:
            GitHubURLError: If the URL is not a valid GitHub repository link.
        """
        clean_url = url.strip().rstrip("/")
        
        # Add https:// if missing
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"
            
        parsed = urlparse(clean_url)
        
        if parsed.netloc not in ("github.com", "www.github.com"):
            raise GitHubURLError(
                f"Invalid host '{parsed.netloc}'. Only github.com repositories are supported."
            )
            
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        
        if len(path_parts) < 2:
            raise GitHubURLError(
                f"Invalid GitHub repository path in '{url}'. Expected format: https://github.com/owner/repo"
            )
            
        owner = path_parts[0]
        repo_name = path_parts[1]
        
        # Remove trailing .git if present
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
            
        # Validate owner and repo against standard GitHub naming rules
        if not re.match(r"^[a-zA-Z0-9._-]+$", owner) or not re.match(r"^[a-zA-Z0-9._-]+$", repo_name):
            raise GitHubURLError(f"Invalid owner '{owner}' or repo name '{repo_name}'")
            
        normalized_url = f"https://github.com/{owner}/{repo_name}"
        return normalized_url, owner, repo_name

    @classmethod
    def calculate_sha256(cls, content: str) -> str:
        """Calculates SHA-256 hash of a string content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def fetch_readme(
        cls, 
        url: str, 
        github_token: Optional[str] = None,
        timeout: int = 15
    ) -> Tuple[str, str, str, str, str]:
        """
        Fetches the README for a given GitHub repository URL.
        
        Args:
            url: GitHub repository URL.
            github_token: Optional personal access token for higher rate limits.
            timeout: HTTP request timeout in seconds.
            
        Returns:
            Tuple of (raw_content, readme_hash, readme_url, owner, repo_name)
        """
        normalized_url, owner, repo_name = cls.parse_github_url(url)
        headers = {
            "User-Agent": "README-RAG-Bot-Indexer/1.0",
            "Accept": "text/plain, text/markdown, application/vnd.github.v3.raw",
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        # Strategy 1: Attempt direct raw.githubusercontent.com downloads
        for branch in cls.COMMON_BRANCHES:
            for filename in cls.README_FILENAMES:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{filename}"
                try:
                    resp = requests.get(raw_url, headers=headers, timeout=timeout)
                    if resp.status_code == 200:
                        content = resp.text
                        if len(resp.content) > IndexerConfig.MAX_README_SIZE_BYTES:
                            raise ReadmeTooLargeError(
                                f"README size ({len(resp.content)} bytes) exceeds the allowed limit of {IndexerConfig.MAX_README_SIZE_BYTES} bytes."
                            )
                        if content.strip():
                            readme_hash = cls.calculate_sha256(content)
                            return content, readme_hash, raw_url, owner, repo_name
                except requests.RequestException:
                    continue

        # Strategy 2: Fallback to GitHub API endpoint for README
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
        try:
            resp = requests.get(api_url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                content = resp.text
                if len(resp.content) > IndexerConfig.MAX_README_SIZE_BYTES:
                    raise ReadmeTooLargeError(
                        f"README size exceeds the allowed limit of {IndexerConfig.MAX_README_SIZE_BYTES} bytes."
                    )
                if content.strip():
                    readme_hash = cls.calculate_sha256(content)
                    return content, readme_hash, api_url, owner, repo_name
            elif resp.status_code == 404:
                raise ReadmeFetchError(
                    f"README file not found in repository {owner}/{repo_name}. Check if the repository is public."
                )
            elif resp.status_code == 403:
                raise ReadmeFetchError(
                    "GitHub API rate limit exceeded or access forbidden. Consider providing a GITHUB_TOKEN."
                )
        except requests.RequestException as e:
            raise ReadmeFetchError(f"Network error while fetching README: {str(e)}")

        raise ReadmeFetchError(
            f"Could not locate a README file for {normalized_url} on branches: {', '.join(cls.COMMON_BRANCHES)}"
        )
