from typing import List, Dict, Any, Optional
import httpx
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError, SYSTEM_GROUNDING_PROMPT


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider for automatic failover."""

    name: str = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        top_p: float = 0.9,
    ):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.model = model or "gemini-1.5-flash"
        self.temperature = temperature
        self.top_p = top_p
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

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
            raise ProviderError("Gemini API key is not configured.", provider="gemini")

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        user_content_parts = []
        user_content_parts.append(
            f"PRODUCT KNOWLEDGE CONTEXT:\n\n{formatted_context}\n\nUSER QUESTION:\n{question}"
        )

        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_GROUNDING_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "\n\n".join(user_content_parts)}]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "topP": self.top_p,
                "maxOutputTokens": 1024,
            }
        }

        # Include previous conversation if present
        if conversation:
            history_contents = []
            for msg in conversation:
                role = "user" if msg.get("role") in ("user", "human") else "model"
                content = msg.get("content", "")
                if content:
                    history_contents.append({
                        "role": role,
                        "parts": [{"text": content}]
                    })
            if history_contents:
                history_contents.append(payload["contents"][0])
                payload["contents"] = history_contents

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise ProviderError(f"Network error calling Gemini API: {exc}", provider="gemini")

            if response.status_code != 200:
                raise ProviderError(
                    f"Gemini API returned HTTP {response.status_code}: {response.text}",
                    provider="gemini",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise ProviderError("Gemini returned empty candidates list.", provider="gemini")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise ProviderError("Gemini response missing text part.", provider="gemini")

                answer = parts[0]["text"].strip()
                return ProviderResponse(
                    answer=answer,
                    model=self.model,
                    provider="gemini",
                    raw_response=data,
                )
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"Failed to parse Gemini response: {exc}", provider="gemini")
