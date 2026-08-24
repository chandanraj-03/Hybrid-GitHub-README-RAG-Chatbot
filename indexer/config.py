"""
Configuration module for the Local Indexing Pipeline.
Handles environment variables, device selection (NVIDIA GPU / CUDA / CPU),
and default hyperparameters for Markdown chunking and embeddings.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env from current directory or parent directories if present
load_dotenv()
load_dotenv(Path(__file__).parent / ".env")

class IndexerConfig:
    # Supabase Credentials
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Embedding Model Settings
    DEFAULT_EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # Chunking Settings
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    
    # Maximum README download size (2 MB limit to prevent excessive memory usage)
    MAX_README_SIZE_BYTES: int = int(os.getenv("MAX_README_SIZE_BYTES", str(2 * 1024 * 1024)))
    
    # Embedding Generation Batch Size
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    
    # Device override (optional: 'cuda', 'cpu')
    DEVICE_OVERRIDE: Optional[str] = os.getenv("DEVICE_OVERRIDE", None)

    @classmethod
    def get_device(cls) -> str:
        """Determines the appropriate PyTorch compute device."""
        if cls.DEVICE_OVERRIDE:
            return cls.DEVICE_OVERRIDE
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @classmethod
    def get_gpu_info(cls) -> dict:
        """Returns diagnostic details about the GPU environment."""
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                device_count = torch.cuda.device_count()
                current_device = torch.cuda.current_device()
                device_name = torch.cuda.get_device_name(current_device)
                capability = torch.cuda.get_device_capability(current_device)
                vram_gb = torch.cuda.get_device_properties(current_device).total_memory / (1024 ** 3)
                return {
                    "cuda_available": True,
                    "device_count": device_count,
                    "device_name": device_name,
                    "compute_capability": f"{capability[0]}.{capability[1]}",
                    "vram_gb": round(vram_gb, 2),
                    "pytorch_version": torch.__version__,
                }
            else:
                return {
                    "cuda_available": False,
                    "device_name": "CPU (No CUDA GPU detected or PyTorch built without CUDA)",
                    "pytorch_version": torch.__version__,
                }
        except ImportError:
            return {
                "cuda_available": False,
                "device_name": "PyTorch not installed",
                "pytorch_version": "N/A",
            }
