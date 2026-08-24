"""
Local Embedding Generator module.
Loads SentenceTransformer models on NVIDIA GPU (CUDA) or CPU fallback,
detects embedding dimensions dynamically, and computes normalized vector embeddings in batches.
"""

from typing import List, Optional
import numpy as np

from indexer.config import IndexerConfig


class EmbeddingGenerator:
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initializes the embedding generator with the specified model and compute device.
        """
        self.model_name = model_name or IndexerConfig.DEFAULT_EMBEDDING_MODEL
        self.device = device or IndexerConfig.get_device()
        self.batch_size = batch_size or IndexerConfig.BATCH_SIZE
        self.model = None
        self.dimension = None

        self._load_model()

    def _load_model(self) -> None:
        """Loads the SentenceTransformer model onto the target device."""
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            # Instantiate model
            self.model = SentenceTransformer(self.model_name, device=self.device)
            
            # Dynamically determine the embedding dimension
            self.dimension = self.model.get_sentence_embedding_dimension()
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{self.model_name}' on device '{self.device}': {str(e)}"
            )

    def get_dimension(self) -> int:
        """Returns the dynamic vector dimension of the loaded embedding model."""
        if self.dimension is None:
            raise RuntimeError("Model is not loaded or dimension is undefined.")
        return int(self.dimension)

    def generate_embeddings(
        self, 
        texts: List[str], 
        show_progress_bar: bool = False
    ) -> List[List[float]]:
        """
        Generates L2-normalized vector embeddings for a list of text strings.
        
        Args:
            texts: List of text strings to embed.
            show_progress_bar: Whether to display a progress bar.
            
        Returns:
            List of Python float lists suitable for pgvector insertion.
        """
        if not texts:
            return []

        if self.model is None:
            raise RuntimeError("Embedding model is not loaded.")

        import torch

        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

        # Convert numpy array to list of float lists
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        return [list(vec) for vec in embeddings]
