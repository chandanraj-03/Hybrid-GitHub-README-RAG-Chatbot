"""
Integration tests for FastAPI endpoints (/api/health, /api/projects/{id}, /api/chat).
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import pytest

from backend.main import app
from backend.generator import FALLBACK_ANSWER
from backend.schemas import SourceItem

client = TestClient(app)


def test_api_health():
    with patch("backend.embeddings.QuestionEmbedder.get_instance") as mock_emb, \
         patch("backend.generator.AnswerGenerator.get_instance") as mock_gen:
        
        mock_emb_inst = MagicMock()
        mock_emb_inst.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        mock_emb.return_value = mock_emb_inst

        mock_gen_inst = MagicMock()
        mock_gen_inst.model_name = "google/flan-t5-small"
        mock_gen_inst.device = "cpu"
        mock_gen.return_value = mock_gen_inst

        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert data["generator_model"] == "google/flan-t5-small"


def test_api_get_project_found():
    mock_proj_data = {
        "id": "proj-uuid-1234",
        "github_url": "https://github.com/fastapi/fastapi",
        "owner": "fastapi",
        "repo_name": "fastapi",
        "readme_hash": "a1b2c3d4e5f6",
        "readme_url": "https://raw.githubusercontent.com/fastapi/fastapi/main/README.md",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimension": 384,
        "indexed_at": "2026-08-24T12:00:00Z",
        "created_at": "2026-08-24T12:00:00Z",
    }

    with patch("backend.supabase_client.SupabaseService.get_instance") as mock_sup:
        mock_instance = MagicMock()
        mock_instance.get_project_by_id.return_value = mock_proj_data
        mock_instance.get_chunk_count.return_value = 14
        mock_sup.return_value = mock_instance

        resp = client.get("/api/projects/proj-uuid-1234")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-uuid-1234"
        assert data["owner"] == "fastapi"
        assert data["chunk_count"] == 14


def test_api_get_project_not_found():
    with patch("backend.supabase_client.SupabaseService.get_instance") as mock_sup:
        mock_instance = MagicMock()
        mock_instance.get_project_by_id.return_value = None
        mock_sup.return_value = mock_instance

        resp = client.get("/api/projects/non-existent-id")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_api_chat_success():
    with patch("backend.embeddings.QuestionEmbedder.get_instance") as mock_emb, \
         patch("backend.retrieval.ReadmeRetriever.retrieve") as mock_retrieve, \
         patch("backend.generator.AnswerGenerator.get_instance") as mock_gen:
        
        # 1. Mock embedder
        mock_emb_inst = MagicMock()
        mock_emb_inst.embed_question.return_value = [0.1] * 384
        mock_emb.return_value = mock_emb_inst

        # 2. Mock retriever
        sample_source = SourceItem(
            chunk_index=0,
            section="Installation",
            section_path="Installation > Setup",
            content="Run pip install -r requirements.txt",
            score=0.91,
        )
        mock_retrieve.return_value = ([sample_source], "### Section: Installation > Setup\nRun pip install -r requirements.txt")

        # 3. Mock generator
        mock_gen_inst = MagicMock()
        mock_gen_inst.generate_answer.return_value = "Install dependencies using pip install -r requirements.txt."
        mock_gen.return_value = mock_gen_inst

        payload = {
            "project_id": "proj-uuid-1234",
            "question": "How do I install the requirements?"
        }

        resp = client.post("/api/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "pip install" in data["answer"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["score"] == 0.91


def test_api_chat_hallucination_fallback():
    with patch("backend.embeddings.QuestionEmbedder.get_instance") as mock_emb, \
         patch("backend.retrieval.ReadmeRetriever.retrieve") as mock_retrieve:
        
        mock_emb_inst = MagicMock()
        mock_emb_inst.embed_question.return_value = [0.1] * 384
        mock_emb.return_value = mock_emb_inst

        # No chunks passed threshold
        mock_retrieve.return_value = ([], "")

        payload = {
            "project_id": "proj-uuid-1234",
            "question": "What is the stock price of this open source project?"
        }

        resp = client.post("/api/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == FALLBACK_ANSWER
        assert data["sources"] == []


def test_api_chat_validation_errors():
    # Empty question
    resp = client.post("/api/chat", json={"project_id": "proj-123", "question": ""})
    assert resp.status_code == 422

    # Oversized question (>500 chars)
    resp = client.post("/api/chat", json={"project_id": "proj-123", "question": "a" * 501})
    assert resp.status_code == 422
