import abc
import math
from typing import List, Tuple, Dict, Any, Optional
from backend.app.rag.chunker import TextChunk


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class BaseVectorStore(abc.ABC):
    """Abstract interface for vector stores."""

    @abc.abstractmethod
    def add_chunks(self, chunks: List[TextChunk], embeddings: List[List[float]]) -> None:
        pass

    @abc.abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 4) -> List[Tuple[TextChunk, float]]:
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        pass

    @abc.abstractmethod
    def count(self) -> int:
        pass


class InMemoryVectorStore(BaseVectorStore):
    """In-memory vector store with cosine similarity ranking."""

    def __init__(self):
        self._chunks: List[TextChunk] = []
        self._embeddings: List[List[float]] = []

    def add_chunks(self, chunks: List[TextChunk], embeddings: List[List[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings.")
        self._chunks.extend(chunks)
        self._embeddings.extend(embeddings)

    def search(self, query_embedding: List[float], top_k: int = 4) -> List[Tuple[TextChunk, float]]:
        if not self._chunks:
            return []

        scored = []
        for chunk, emb in zip(self._chunks, self._embeddings):
            score = cosine_similarity(query_embedding, emb)
            scored.append((chunk, score))

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        self._chunks.clear()
        self._embeddings.clear()

    def count(self) -> int:
        return len(self._chunks)
