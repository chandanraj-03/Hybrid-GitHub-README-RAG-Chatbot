from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

router = APIRouter(tags=["Chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of message sender: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question about the GitHub repository")
    conversation: Optional[List[ChatMessage]] = Field(default=None, description="Previous conversation history")
    top_k: Optional[int] = Field(default=None, description="Override top_k retrieved chunks")


class SourceCitation(BaseModel):
    file: str
    section: str


class FailoverHop(BaseModel):
    provider: str
    reason: str


class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    sources: List[SourceCitation]
    failover: bool = False
    failover_reason: Optional[str] = None
    failover_trail: List[FailoverHop] = Field(default_factory=list, description="Chain of preceding failed provider hops")
    retrieved_chunks_count: int = 0


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, request: Request) -> ChatResponse:
    """Answers user queries grounded solely in the synchronized GitHub README."""
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="RAG orchestrator not initialized.")

    conversation_dicts = None
    if payload.conversation:
        conversation_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in payload.conversation
        ]

    try:
        result = await orchestrator.answer_question(
            question=payload.message,
            conversation=conversation_dicts,
            top_k=payload.top_k,
        )

        return ChatResponse(
            answer=result["answer"],
            provider=result["provider"],
            model=result["model"],
            sources=[
                SourceCitation(file=s.get("file", "README.md"), section=s.get("section", "Overview"))
                for s in result.get("sources", [])
            ],
            failover=result.get("failover", False),
            failover_reason=result.get("failover_reason"),
            failover_trail=[
                FailoverHop(provider=h.get("provider", ""), reason=h.get("reason", ""))
                for h in result.get("failover_trail", [])
            ],
            retrieved_chunks_count=result.get("retrieved_chunks_count", 0),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
