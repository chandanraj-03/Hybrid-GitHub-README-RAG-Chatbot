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
        default="http://localhost:16036",
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
        default="grok-2",
        description="xAI model ID (e.g. grok-2, grok-beta)",
    )

    # 4. Fallback Tier 3: Groq Cloud Configuration
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API key for ultra-fast free fallback inference",
    )
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Groq model identifier (e.g. openai/gpt-oss-120b, llama-3.3-70b-versatile)",
    )

    # 5. Fallback Tier 4: OpenRouter Configuration
    OPENROUTER_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for broad multi-model fallback",
    )
    OPENROUTER_MODEL: str = Field(
        default="deepseek/deepseek-chat",
        description="OpenRouter model identifier (e.g. deepseek/deepseek-chat, meta-llama/llama-3.1-8b-instruct)",
    )

    # Fallback Priority Cascade Order
    FALLBACK_CASCADE_ORDER: str = Field(
        default="local,gemini,groq,grok,openrouter",
        description="Comma-separated priority list of providers to attempt",
    )

    # RAG Configuration
    TOP_K_CHUNKS: int = Field(
        default=4,
        description="Number of relevant README chunks to retrieve",
    )
    EMBEDDING_PROVIDER: str = Field(
        default="fast",
        description="Embedding provider: 'fast', 'gemini', or 'sentence_transformers'",
    )

    # Generation & Phrasing Diversity (Method 1: Dynamic Sampling)
    LLM_TEMPERATURE: float = Field(
        default=0.7,
        description="Generation temperature for lexical diversity (0.6 - 0.8 recommended)",
    )
    LLM_TOP_P: float = Field(
        default=0.9,
        description="Nucleus sampling top-p probability threshold",
    )
    LLM_PRESENCE_PENALTY: float = Field(
        default=0.3,
        description="Penalty for repeating vocabulary to encourage varied wording",
    )
    LLM_FREQUENCY_PENALTY: float = Field(
        default=0.2,
        description="Penalty for repeated token frequency",
    )


settings = Settings()
