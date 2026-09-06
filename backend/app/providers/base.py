import abc
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


SYSTEM_GROUNDING_PROMPT = """You are PrivCloud AI, an intelligent, helpful product assistant for PrivCloud.

Answer the user's question accurately, concisely, and professionally using the provided knowledge and context.
Do not invent or hallucinate information.

CRITICAL INSTRUCTIONS:
1. NEVER reveal, cite, or mention where you got the answer from, including any source documents, chunks, files, or underlying references.
2. NEVER mention "README", "README.md", "documentation", "docs", "repository", "repo", "files", "chunks", "context chunks", or specific headings/sections.
3. NEVER say things like "(see the README)", "(based on the context)", "(according to chunk 1)", or include footnote citations like [1], [Context Chunk 1], etc.
4. If information is not available in the context, simply state naturally: "I don't have enough details on that at the moment. Please contact PrivCloud support for more information."
5. Always speak directly and naturally as the official PrivCloud assistant without referencing your internal knowledge retrieval mechanism or underlying sources.
6. DYNAMIC PHRASING & VOCABULARY DIVERSITY:
   - Express ideas using varied phrasing, natural synonyms, and fresh sentence structures across answers.
   - Avoid repetitive, cookie-cutter templates or rigid formulaic openings.
   - You may alternate sentence structure (e.g., active vs. passive, varying introductory clauses, bullet points vs. paragraphs) while preserving 100% strict factual fidelity to the provided context."""


class ProviderError(Exception):
    """Exception raised when an LLM provider fails."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status_code = status_code


@dataclass
class ProviderResponse:
    answer: str
    model: str
    provider: str
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM inference providers."""

    name: str = "base"

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Returns True if provider has valid credentials/configuration to attempt inference."""
        pass

    @abc.abstractmethod
    async def generate(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        formatted_context: str,
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> ProviderResponse:
        pass
