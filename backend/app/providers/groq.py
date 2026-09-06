from typing import List, Dict, Any, Optional
import httpx
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError, SYSTEM_GROUNDING_PROMPT


class GroqProvider(BaseLLMProvider):
    """Groq Cloud API Provider offering low-latency LPU inference fallback."""

    name: str = "groq"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.7,
        top_p: float = 0.9,
        presence_penalty: float = 0.3,
        frequency_penalty: float = 0.2,
    ):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        clean_model = (model or "openai/gpt-oss-120b").strip()
        if ":" in clean_model and not "/" in clean_model:
            clean_model = clean_model.replace(":", "/")
        self.model = clean_model
        self.temperature = temperature
        self.top_p = top_p
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.base_url = "https://api.groq.com/openai/v1"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        formatted_context: str,
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError("Groq API key is not configured.", provider="groq")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-README-RAG-Chatbot",
        }

        user_content = f"PRODUCT KNOWLEDGE CONTEXT:\n\n{formatted_context}\n\nUSER QUESTION:\n{question}"

        messages = [{"role": "system", "content": SYSTEM_GROUNDING_PROMPT}]

        if conversation:
            for msg in conversation:
                role = "user" if msg.get("role") in ("user", "human") else "assistant"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise ProviderError(f"Network error calling Groq API: {exc}", provider="groq")

            if response.status_code != 200:
                raise ProviderError(
                    f"Groq API returned HTTP {response.status_code}: {response.text}",
                    provider="groq",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise ProviderError("Groq returned empty choices array.", provider="groq")

                answer = choices[0].get("message", {}).get("content", "").strip()
                if not answer:
                    raise ProviderError("Groq returned empty response text.", provider="groq")

                return ProviderResponse(
                    answer=answer,
                    model=self.model,
                    provider="groq",
                    raw_response=data,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"Failed to parse Groq response: {exc}", provider="groq")
