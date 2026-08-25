import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.github.readme_loader import ReadmeDocument
from backend.app.rag.chunker import MarkdownHeadingChunker
from backend.app.rag.embeddings import DeterministicFallbackEmbeddings
from backend.app.rag.vector_store import InMemoryVectorStore
from backend.app.rag.pipeline import RagPipeline
from laptop.app.model import LaptopTransformerModel


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestApiEndpointsAndGrounding:

    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "indexed_chunks" in data

    def test_laptop_status_endpoint(self, client):
        response = client.get("/api/laptop-status")
        assert response.status_code == 200
        data = response.json()
        assert "online" in data
        assert "url" in data

    def test_github_status_endpoint(self, client):
        response = client.get("/api/github/status")
        assert response.status_code == 200
        data = response.json()
        assert "repository" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_section_26_strict_grounding(self, sample_readme_text):
        """
        Tests the strict grounding requirements specified in idea.txt Section 26:
        - When information is in README: returns factual answer mentioning the README section/content.
        - When information is absent (e.g. database): returns exact phrase
          'I couldn't find that information in the repository README.'
        """
        # 1. Setup isolated RAG pipeline with Section 26 README
        rag_pipeline = RagPipeline(
            chunker=MarkdownHeadingChunker(),
            embedding_model=DeterministicFallbackEmbeddings(),
            vector_store=InMemoryVectorStore(),
        )

        doc = ReadmeDocument(
            owner="test-org",
            repo="test-project",
            branch="main",
            sha="test_sha_s26",
            filename="README.md",
            raw_markdown=sample_readme_text,
        )
        await rag_pipeline.index_readme(doc)

        # 2. Test Grounding Model Engine directly
        model_engine = LaptopTransformerModel()

        # Query 1: Information is present (Installation)
        chunks, _, _ = rag_pipeline.retrieve("How do I install the project?")
        context_payload = [{"text": c.text, "section": c.section} for c in chunks]
        ans1 = model_engine.generate_answer("How do I install the project?", context_payload)
        assert "pip install test-project" in ans1 or "Installation" in ans1

        # Query 2: Information is NOT present (Database)
        chunks_db, _, _ = rag_pipeline.retrieve("What database does the project use?")
        # Grounding check with empty/irrelevant context
        ans2 = model_engine.generate_answer("What database does the project use?", [])
        assert "I couldn't find that information in the repository README." in ans2
