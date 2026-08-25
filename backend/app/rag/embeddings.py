import abc
import hashlib
import math
import re
from typing import List, Optional


class BaseEmbeddings(abc.ABC):
    """Abstract base class for embedding models."""

    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abc.abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass


class FastLightweightEmbeddings(BaseEmbeddings):
    """
    Ultra-lightweight, zero-memory deterministic subword vectorizer.
    Runs in <1ms without PyTorch or HuggingFace weights, ideal for 512MB RAM cloud tiers.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _text_to_vec(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec

        for token in tokens:
            # Word hash
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.5

            # Subword 3-grams for fuzzy matching
            for i in range(max(1, len(token) - 2)):
                tri = token[i:i+3]
                h_tri = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16)
                vec[h_tri % self.dim] += 0.8

        # L2 normalization for accurate cosine similarity
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vec(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._text_to_vec(text)


# Backwards compatibility alias
DeterministicFallbackEmbeddings = FastLightweightEmbeddings


class GeminiApiEmbeddings(BaseEmbeddings):
    """
    Cloud-based embeddings via Google Gemini text-embedding-004 API.
    Zero local RAM overhead.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.fallback = FastLightweightEmbeddings()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import httpx
        if not self.api_key:
            return self.fallback.embed_documents(texts)
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key={self.api_key}"
            requests_body = [{"model": "models/text-embedding-004", "content": {"parts": [{"text": t[:2048]}]}} for t in texts]
            resp = httpx.post(url, json={"requests": requests_body}, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json()
                return [e["values"] for e in data.get("embeddings", [])]
        except Exception:
            pass
        return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        docs = self.embed_documents([text])
        return docs[0] if docs else [0.0] * 384


class SentenceTransformerEmbeddings(BaseEmbeddings):
    """Optional heavy transformer embeddings when RAM > 1GB is available."""

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


def get_embedding_model(provider: str = "fast", gemini_api_key: Optional[str] = None) -> BaseEmbeddings:
    """Factory returning memory-safe embedding engine."""
    provider_clean = (provider or "fast").lower().strip()

    if provider_clean in ("gemini", "google") and gemini_api_key:
        return GeminiApiEmbeddings(api_key=gemini_api_key)

    if provider_clean in ("sentence_transformers", "st"):
        try:
            return SentenceTransformerEmbeddings()
        except Exception:
            return FastLightweightEmbeddings()

    return FastLightweightEmbeddings()
