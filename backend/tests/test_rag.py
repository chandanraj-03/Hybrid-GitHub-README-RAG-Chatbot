import pytest
from backend.app.rag.chunker import MarkdownHeadingChunker, TextChunk
from backend.app.rag.embeddings import DeterministicFallbackEmbeddings
from backend.app.rag.vector_store import InMemoryVectorStore, cosine_similarity
from backend.app.rag.retriever import ReadmeRetriever
from backend.app.rag.pipeline import RagPipeline
from backend.app.github.readme_loader import ReadmeDocument


class TestMarkdownChunker:

    def test_chunk_headings_and_metadata(self, sample_readme_text):
        chunker = MarkdownHeadingChunker(max_chunk_size=500)
        chunks = chunker.chunk_markdown(
            sample_readme_text,
            repository="test/repo",
            file="README.md",
            branch="main",
        )

        assert len(chunks) >= 3
        sections = [c.metadata["section"] for c in chunks]
        assert "Installation" in sections
        assert "Configuration" in sections
        assert "Usage" in sections

        for c in chunks:
            assert c.metadata["repository"] == "test/repo"
            assert c.metadata["file"] == "README.md"
            assert c.metadata["branch"] == "main"
            assert c.metadata["heading_level"] >= 1

    def test_code_blocks_preserved(self, sample_readme_text):
        chunker = MarkdownHeadingChunker(max_chunk_size=400)
        chunks = chunker.chunk_markdown(
            sample_readme_text,
            repository="test/repo",
        )

        # Find installation chunk
        install_chunks = [c for c in chunks if c.metadata["section"] == "Installation"]
        assert len(install_chunks) > 0
        install_text = install_chunks[0].text

        assert "```bash" in install_text
        assert "pip install test-project" in install_text
        assert "```" in install_text


class TestVectorStoreAndRetriever:

    def test_cosine_similarity(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]

        assert cosine_similarity(v1, v2) == pytest.approx(1.0)
        assert cosine_similarity(v1, v3) == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_end_to_end_rag_pipeline_retrieval(self, sample_readme_text):
        embedding_model = DeterministicFallbackEmbeddings()
        vector_store = InMemoryVectorStore()
        chunker = MarkdownHeadingChunker()

        pipeline = RagPipeline(
            chunker=chunker,
            embedding_model=embedding_model,
            vector_store=vector_store,
        )

        doc = ReadmeDocument(
            owner="test-owner",
            repo="test-project",
            branch="main",
            sha="sha123",
            filename="README.md",
            raw_markdown=sample_readme_text,
        )

        num_chunks = await pipeline.index_readme(doc)
        assert num_chunks > 0
        assert pipeline.count() == num_chunks

        # Query for installation
        chunks, formatted_ctx, sources = pipeline.retrieve("How do I install the project?")
        assert len(chunks) > 0
        assert "Installation" in [c.section for c in chunks]
        assert "pip install test-project" in formatted_ctx
        assert any(s["section"] == "Installation" for s in sources)
