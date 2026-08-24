"""
Question Embedding Module for Render Backend.
Loads SentenceTransformer once at startup and computes normalized vectors for user questions.
"""

from typing import List, Optional
import numpy as np

from backend.config import BackendConfig


class QuestionEmbedder:
    _instance: Optional["QuestionEmbedder"] = None

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or BackendConfig.EMBEDDING_MODEL_NAME
        self.device = "cpu"
        self.model = None
        self.dimension = None
        self._load_model()

    @classmethod
    def get_instance(cls) -> "QuestionEmbedder":
        """Singleton accessor to ensure the model is loaded only once."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self) -> None:
        """Loads SentenceTransformer on CPU for minimal memory footprint."""
        from sentence_transformers import SentenceTransformer
        import torch

        # Force CPU device for Render deployment
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_question(self, question: str) -> List[float]:
        """
        Computes L2-normalized vector embedding for a single user question.
        Applies model-specific query instructions (e.g. for BGE models).
        """
        if self.model is None:
            raise RuntimeError("Question embedder model is not initialized.")

        import torch

        # BGE models require an instruction prefix for query embeddings in retrieval
        if "bge" in self.model_name.lower():
            text_to_embed = f"Represent this sentence for searching relevant passages: {question.strip()}"
        else:
            text_to_embed = question.strip()

        with torch.no_grad():
            vec = self.model.encode(
                text_to_embed,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

        if isinstance(vec, np.ndarray):
            return vec.tolist()
        return list(vec)
