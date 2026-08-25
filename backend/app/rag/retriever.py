from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from backend.app.rag.embeddings import BaseEmbeddings
from backend.app.rag.vector_store import BaseVectorStore
from backend.app.rag.chunker import TextChunk


@dataclass
class RetrievedChunk:
    text: str
    section: str
    heading_level: int
    file: str
    repository: str
    branch: str
    score: float
    chunk_id: Optional[str] = None


class ReadmeRetriever:
    """Retrieves relevant README chunks for user queries."""

    def __init__(self, vector_store: BaseVectorStore, embedding_model: BaseEmbeddings):
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.0,
    ) -> List[RetrievedChunk]:
        """Performs vector search and converts results to RetrievedChunk objects."""
        if not query.strip() or self.vector_store.count() == 0:
            return []

        query_vector = self.embedding_model.embed_query(query)
        scored_results = self.vector_store.search(query_vector, top_k=top_k)

        chunks: List[RetrievedChunk] = []
        for chunk, score in scored_results:
            if score >= min_score:
                meta = chunk.metadata or {}
                chunks.append(
                    RetrievedChunk(
                        text=chunk.text,
                        section=meta.get("section", "Overview"),
                        heading_level=meta.get("heading_level", 1),
                        file=meta.get("file", "README.md"),
                        repository=meta.get("repository", "unknown"),
                        branch=meta.get("branch", "main"),
                        score=score,
                        chunk_id=chunk.chunk_id,
                    )
                )

        return chunks

    @staticmethod
    def format_context_for_prompt(chunks: List[RetrievedChunk]) -> str:
        """Formats retrieved chunks into a standardized context block for LLM prompts."""
        if not chunks:
            return "No README context available."

        formatted_blocks = []
        for i, chunk in enumerate(chunks, 1):
            block = f"--- [Context Chunk {i}: Section '{chunk.section}'] ---\n{chunk.text.strip()}"
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

    @staticmethod
    def extract_sources(chunks: List[RetrievedChunk]) -> List[Dict[str, str]]:
        """Extracts unique source citations for the frontend API response."""
        seen = set()
        sources = []
        for c in chunks:
            key = (c.file, c.section)
            if key not in seen:
                seen.add(key)
                sources.append({
                    "file": c.file,
                    "section": c.section,
                })
        return sources
