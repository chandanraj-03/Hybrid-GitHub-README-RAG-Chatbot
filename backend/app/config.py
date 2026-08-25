import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "GitHub README Hybrid RAG"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False

    # GitHub Configuration
    GITHUB_REPO_URL: str = Field(
        default="https://github.com/tiangolo/fastapi",
        description="GitHub repository URL to use as knowledge base",
    )
    GITHUB_BRANCH: Optional[str] = Field(
        default=None,
        description="Target branch. If empty or None, uses repo default branch",
    )
    GITHUB_TOKEN: Optional[str] = Field(
        default=None,
        description="Optional personal access token for private repositories or higher rate limits",
    )

    # 1. Primary: Local Laptop LLM Configuration
    LAPTOP_API_URL: Optional[str] = Field(
        default="http://localhost:8000",
        description="Base URL for local laptop LLM API or Cloudflare tunnel URL",
    )
    LAPTOP_API_TOKEN: Optional[str] = Field(
        default="secret-laptop-token",
        description="Bearer token for laptop authentication",
    )
    LOCAL_LLM_TIMEOUT: float = Field(
        default=25.0,
        description="Timeout in seconds before falling back from local model",
    )

    # 2. Fallback Tier 1: Google Gemini Configuration
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for primary cloud fallback",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model ID to use for inference",
    )

    # 3. Fallback Tier 2: xAI Grok Configuration
    GROK_API_KEY: Optional[str] = Field(
        default=None,
        description="xAI API key for Grok fallback inference",
    )
    GROK_MODEL: str = Field(
        default="grok-2-latest",
        description="xAI model ID (e.g. grok-2-latest, grok-beta)",
    )

    # 4. Fallback Tier 3: OpenRouter Configuration
    OPENROUTER_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for broad multi-model fallback",
    )
    OPENROUTER_MODEL: str = Field(
        default="meta-llama/llama-3.3-70b-instruct",
        description="OpenRouter model identifier",
    )

    # 5. Fallback Tier 4: Groq Cloud Configuration
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API key for low-latency LPU fallback inference",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model identifier",
    )

    # Fallback Priority Cascade Order
    FALLBACK_CASCADE_ORDER: str = Field(
        default="local,gemini,grok,openrouter,groq",
        description="Comma-separated priority list of providers to attempt",
    )

    # RAG Configuration
    TOP_K_CHUNKS: int = Field(
        default=4,
        description="Number of relevant README chunks to retrieve",
    )
    EMBEDDING_PROVIDER: str = Field(
        default="sentence_transformers",
        description="Embedding provider: 'sentence_transformers', 'gemini', or 'local'",
    )


settings = Settings()
