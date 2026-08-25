from typing import List, Dict, Any, Optional
import httpx
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError, SYSTEM_GROUNDING_PROMPT


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API Provider offering broad multi-model routing fallback."""

    name: str = "openrouter"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.3-70b-instruct",
    ):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.model = model or "meta-llama/llama-3.3-70b-instruct"
        self.base_url = "https://openrouter.ai/api/v1"

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
            raise ProviderError("OpenRouter API key is not configured.", provider="openrouter")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rag-chatbot",
            "X-Title": "GitHub README RAG Chatbot",
        }

        user_content = f"README CONTEXT:\n\n{formatted_context}\n\nUSER QUESTION:\n{question}"

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
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise ProviderError(f"Network error calling OpenRouter API: {exc}", provider="openrouter")

            if response.status_code != 200:
                raise ProviderError(
                    f"OpenRouter API returned HTTP {response.status_code}: {response.text}",
                    provider="openrouter",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise ProviderError("OpenRouter returned empty choices array.", provider="openrouter")

                answer = choices[0].get("message", {}).get("content", "").strip()
                if not answer:
                    raise ProviderError("OpenRouter returned empty response text.", provider="openrouter")

                actual_model = data.get("model", self.model)

                return ProviderResponse(
                    answer=answer,
                    model=actual_model,
                    provider="openrouter",
                    raw_response=data,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"Failed to parse OpenRouter response: {exc}", provider="openrouter")
