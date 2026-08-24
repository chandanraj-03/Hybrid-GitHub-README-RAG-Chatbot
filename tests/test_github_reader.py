"""
Unit tests for GitHub URL parsing, integrity hashing, and README retrieval.
"""

import hashlib
import pytest
from unittest.mock import patch, MagicMock

from indexer.github_reader import (
    GitHubReader,
    GitHubURLError,
    ReadmeFetchError,
    ReadmeTooLargeError,
)


def test_parse_github_url_valid():
    cases = [
        ("https://github.com/fastapi/fastapi", "https://github.com/fastapi/fastapi", "fastapi", "fastapi"),
        ("http://github.com/psf/requests/", "https://github.com/psf/requests", "psf", "requests"),
        ("github.com/pallets/flask.git", "https://github.com/pallets/flask", "pallets", "flask"),
        ("https://www.github.com/tiangolo/typer", "https://github.com/tiangolo/typer", "tiangolo", "typer"),
    ]
    for raw, expected_url, expected_owner, expected_repo in cases:
        url, owner, repo = GitHubReader.parse_github_url(raw)
        assert url == expected_url
        assert owner == expected_owner
        assert repo == expected_repo


def test_parse_github_url_invalid():
    invalid_cases = [
        "https://gitlab.com/owner/repo",
        "https://google.com",
        "https://github.com",
        "https://github.com/justonepart",
        "invalid://url",
    ]
    for raw in invalid_cases:
        with pytest.raises(GitHubURLError):
            GitHubReader.parse_github_url(raw)


def test_calculate_sha256():
    sample_text = "# Sample Project\nThis is a test readme."
    expected_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()
    assert GitHubReader.calculate_sha256(sample_text) == expected_hash


@patch("indexer.github_reader.requests.get")
def test_fetch_readme_success(mock_get):
    sample_content = "# Awesome Project\nWelcome to our project!"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_content
    mock_resp.content = sample_content.encode("utf-8")
    mock_get.return_value = mock_resp

    content, r_hash, r_url, owner, repo = GitHubReader.fetch_readme("https://github.com/user/test-repo")
    assert content == sample_content
    assert owner == "user"
    assert repo == "test-repo"
    assert r_hash == hashlib.sha256(sample_content.encode("utf-8")).hexdigest()


@patch("indexer.github_reader.requests.get")
def test_fetch_readme_not_found(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    with pytest.raises(ReadmeFetchError):
        GitHubReader.fetch_readme("https://github.com/nonexistent/repo")
