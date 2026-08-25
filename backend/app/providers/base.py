import abc
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


SYSTEM_GROUNDING_PROMPT = """You are a GitHub README assistant.

Answer the user's question using ONLY the supplied README context.
Do not invent information.
If the answer cannot be found in the README context, say:
"I couldn't find that information in the repository README."

Do not pretend that information exists in the README when it does not.
When useful, mention the relevant README section."""


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
