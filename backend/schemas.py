"""
Pydantic Schemas for the FastAPI Chatbot API.
Defines strict input and output validation contracts.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    project_id: str = Field(
        ...,
        description="UUID of the indexed GitHub project in Supabase",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    question: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="The user query regarding the repository README",
        examples=["What technologies and backend frameworks are used?"],
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Optional override for number of retrieved chunks (1-10)",
    )
    similarity_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional override for cosine similarity threshold",
    )

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("project_id cannot be empty")
        return clean

    @field_validator("question")
    @classmethod
    def clean_question(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("question cannot be whitespace only")
        return clean


class SourceItem(BaseModel):
    chunk_index: Optional[int] = Field(None, description="Index of the chunk in the README")
    section: str = Field(..., description="Section title", examples=["Backend Architecture"])
    section_path: str = Field(..., description="Full hierarchy breadcrumb", examples=["Architecture > Backend"])
    content: str = Field(..., description="Retrieved markdown chunk text")
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)", examples=[0.87])


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Generated answer grounded strictly in README context")
    sources: List[SourceItem] = Field(default_factory=list, description="Top relevant sources used")
    project_id: str = Field(..., description="Project identifier")
    model_used: str = Field(..., description="Transformer generator model name")


class ProjectResponse(BaseModel):
    id: str
    github_url: str
    owner: str
    repo_name: str
    readme_hash: Optional[str] = None
    readme_url: Optional[str] = None
    embedding_model: str
    embedding_dimension: int
    chunk_count: int
    indexed_at: Optional[str] = None
    created_at: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    device: str
    embedding_model: str
    generator_model: str
