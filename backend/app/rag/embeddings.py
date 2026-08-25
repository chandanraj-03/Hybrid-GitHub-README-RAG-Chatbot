import abc
import hashlib
import math
from typing import List


class BaseEmbeddings(abc.ABC):
    """Abstract base class for embedding models."""

    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abc.abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass


class SentenceTransformerEmbeddings(BaseEmbeddings):
    """Embeddings using local sentence-transformers model (e.g. all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()


class DeterministicFallbackEmbeddings(BaseEmbeddings):
    """
    Lightweight deterministic n-gram vectorizer for environments
    where PyTorch/SentenceTransformers weights should not be loaded.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _text_to_vec(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = text.lower().split()
        if not tokens:
            return vec

        for token in tokens:
            # Word hashing trick
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0

            # Also hash character 3-grams
            for i in range(max(1, len(token) - 2)):
                tri = token[i:i+3]
                h_tri = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16)
                idx_tri = h_tri % self.dim
                vec[idx_tri] += 0.5

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vec(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._text_to_vec(text)


def get_embedding_model(provider: str = "sentence_transformers") -> BaseEmbeddings:
    """Factory to instantiate the appropriate embedding provider with graceful fallback."""
    if provider.lower() in ("sentence_transformers", "st"):
        try:
            return SentenceTransformerEmbeddings()
        except Exception as e:
            print(f"[RAG] Warning: sentence-transformers initialization failed ({e}), falling back to deterministic.")
            return DeterministicFallbackEmbeddings()
    return DeterministicFallbackEmbeddings()
