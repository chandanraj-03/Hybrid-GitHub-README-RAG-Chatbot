"""
Backend Configuration for Render Chatbot Server.
Loads environment variables and sets defaults tailored for low-memory CPU environments.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv(override=True)
load_dotenv(Path(__file__).parent / ".env", override=True)
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

class BackendConfig:
    # Supabase connection
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    
    # Use service key if available, otherwise anon key
    @classmethod
    def get_supabase_key(cls) -> str:
        return cls.SUPABASE_SERVICE_ROLE_KEY or cls.SUPABASE_ANON_KEY

    # Embedding Model (Must match indexer model: 384 dim for all-MiniLM-L6-v2)
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Local Generation Model
    GENERATOR_MODEL_NAME: str = os.getenv(
        "GENERATOR_MODEL", "google/flan-t5-small"
    )

    # RAG Retrieval Settings
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.25"))
    
    # Generation Settings
    MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "128"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    
    # Input Constraints
    MAX_QUESTION_LENGTH: int = int(os.getenv("MAX_QUESTION_LENGTH", "500"))

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        origin.strip() 
        for origin in os.getenv("CORS_ORIGINS", "*").split(",") 
        if origin.strip()
    ]
