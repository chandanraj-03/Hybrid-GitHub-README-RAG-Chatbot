from typing import List, Dict, Any, Optional
import httpx
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError, SYSTEM_GROUNDING_PROMPT


class GrokProvider(BaseLLMProvider):
    """xAI Grok API Provider for high-capacity reasoning fallback."""

    name: str = "grok"

    def __init__(self, api_key: Optional[str] = None, model: str = "grok-2-latest"):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.model = model or "grok-2-latest"
        self.base_url = "https://api.x.ai/v1"

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
            raise ProviderError("xAI Grok API key is not configured.", provider="grok")

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
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise ProviderError(f"Network error calling xAI Grok API: {exc}", provider="grok")

            if response.status_code != 200:
                raise ProviderError(
                    f"xAI Grok API returned HTTP {response.status_code}: {response.text}",
                    provider="grok",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise ProviderError("Grok returned empty choices array.", provider="grok")

                answer = choices[0].get("message", {}).get("content", "").strip()
                if not answer:
                    raise ProviderError("Grok returned empty response text.", provider="grok")

                return ProviderResponse(
                    answer=answer,
                    model=self.model,
                    provider="grok",
                    raw_response=data,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"Failed to parse xAI Grok response: {exc}", provider="grok")
