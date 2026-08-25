from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LaptopSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "laptop/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model Settings
    LOCAL_MODEL_NAME: str = Field(
        default="Qwen/Qwen2.5-0.5B-Instruct",
        description="HuggingFace model identifier or local directory path",
    )
    LAPTOP_API_TOKEN: str = Field(
        default="secret-laptop-token",
        description="Bearer token for securing laptop LLM endpoint over Cloudflare Tunnel",
    )
    PORT: int = Field(
        default=8000,
        description="Port for laptop FastAPI server",
    )
    DEVICE: str = Field(
        default="auto",
        description="PyTorch device: 'auto', 'cuda', or 'cpu'",
    )
    MAX_NEW_TOKENS: int = Field(
        default=512,
        description="Max new generation tokens",
    )
    TEMPERATURE: float = Field(
        default=0.2,
        description="Generation temperature",
    )
    USE_LIGHTWEIGHT_ENGINE: bool = Field(
        default=False,
        description="Use fast extractive generator if full transformers model is not loaded",
    )


laptop_settings = LaptopSettings()
