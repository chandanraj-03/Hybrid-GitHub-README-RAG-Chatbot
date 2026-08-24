"""
Unit tests for Local Embedding Generator and Question Embedder.
"""

import math
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from indexer.embedding_generator import EmbeddingGenerator
from backend.embeddings import QuestionEmbedder


def test_embedding_generator_mocked():
    with patch("sentence_transformers.SentenceTransformer") as MockST:
        mock_instance = MagicMock()
        mock_instance.get_sentence_embedding_dimension.return_value = 384
        # Return a normalized 384-dimensional vector
        dummy_vec = np.zeros((2, 384), dtype=np.float32)
        dummy_vec[:, 0] = 1.0  # Unit vector
        mock_instance.encode.return_value = dummy_vec
        MockST.return_value = mock_instance

        generator = EmbeddingGenerator(model_name="sentence-transformers/all-MiniLM-L6-v2", device="cpu")
        
        assert generator.get_dimension() == 384
        
        embeddings = generator.generate_embeddings(["Hello world", "FastAPI RAG"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384
        
        # Check normalization (L2 norm should be 1.0)
        norm = math.sqrt(sum(x * x for x in embeddings[0]))
        assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_question_embedder_mocked():
    with patch("sentence_transformers.SentenceTransformer") as MockST:
        mock_instance = MagicMock()
        mock_instance.get_sentence_embedding_dimension.return_value = 384
        dummy_vec = np.zeros(384, dtype=np.float32)
        dummy_vec[0] = 1.0
        mock_instance.encode.return_value = dummy_vec
        MockST.return_value = mock_instance

        embedder = QuestionEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vec = embedder.embed_question("How do I install the package?")

        assert len(vec) == 384
        assert math.isclose(vec[0], 1.0)
