"""
Unit tests for Retrieval and Project Isolation.
"""

from unittest.mock import MagicMock
from backend.retrieval import ReadmeRetriever
from backend.supabase_client import SupabaseService


def test_retriever_formats_sources_and_filters_threshold():
    mock_supabase = MagicMock(spec=SupabaseService)
    
    # Mock RPC search results: 2 items above threshold, 1 below
    mock_supabase.search_chunks.return_value = [
        {
            "id": "chunk-1",
            "project_id": "proj-123",
            "chunk_index": 0,
            "section_title": "Installation",
            "section_path": "Installation > Quickstart",
            "content": "pip install readme-bot",
            "similarity": 0.85,
        },
        {
            "id": "chunk-2",
            "project_id": "proj-123",
            "chunk_index": 1,
            "section_title": "Usage",
            "section_path": "Usage > Run",
            "content": "python run.py",
            "similarity": 0.72,
        },
        {
            "id": "chunk-3",
            "project_id": "proj-123",
            "chunk_index": 2,
            "section_title": "Unrelated",
            "section_path": "Unrelated",
            "content": "Some noise",
            "similarity": 0.20,
        },
    ]

    retriever = ReadmeRetriever(mock_supabase)
    sources, context = retriever.retrieve(
        project_id="proj-123",
        question_embedding=[0.1] * 384,
        top_k=3,
        similarity_threshold=0.50,
    )

    # Check that chunk-3 was filtered out
    assert len(sources) == 2
    assert sources[0].section == "Installation"
    assert sources[0].score == 0.85
    assert sources[1].section == "Usage"
    assert sources[1].score == 0.72

    # Verify context construction
    assert "### Section: Installation > Quickstart" in context
    assert "pip install readme-bot" in context
    assert "### Section: Usage > Run" in context
    assert "Some noise" not in context

    # Check project isolation parameter was passed to Supabase RPC
    mock_supabase.search_chunks.assert_called_once_with(
        project_id="proj-123",
        query_embedding=[0.1] * 384,
        match_count=3,
        similarity_threshold=0.50,
    )
