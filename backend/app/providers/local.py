import asyncio
from typing import List, Dict, Any, Optional
import httpx
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError


class LocalLaptopProvider(BaseLLMProvider):
    """
    Client for local laptop LLM service (FastAPI running transformer model).
    Supports Cloudflare Quick Tunnel or direct localhost connection with Bearer auth.
    """

    name: str = "local"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        auth_token: Optional[str] = None,
        timeout: float = 4.0,
    ):
        self.base_url = base_url.rstrip("/") if base_url else "http://localhost:8000"
        self.auth_token = auth_token.strip() if auth_token and auth_token.strip() else None
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GitHub-README-RAG-Backend",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def check_health(self) -> Dict[str, Any]:
        """Checks if local laptop service is online and healthy."""
        url = f"{self.base_url}/health"
        async with httpx.AsyncClient(timeout=min(self.timeout, 3.0)) as client:
            try:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    return {"online": True, "details": resp.json()}
                return {"online": False, "status_code": resp.status_code, "error": resp.text}
            except Exception as exc:
                return {"online": False, "error": str(exc)}

    async def generate(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        formatted_context: str,
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> ProviderResponse:
        url = f"{self.base_url}/generate"
        payload = {
            "question": question,
            "context": [
                {
                    "text": chunk.get("text", ""),
                    "section": chunk.get("section", "Overview"),
                }
                for chunk in context_chunks
            ],
            "conversation": conversation or [],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    f"Laptop LLM request timed out after {self.timeout}s: {exc}",
                    provider="local",
                )
            except httpx.RequestError as exc:
                raise ProviderError(
                    f"Could not connect to Laptop LLM at '{url}': {exc}",
                    provider="local",
                )

            if response.status_code != 200:
                raise ProviderError(
                    f"Laptop LLM responded with HTTP {response.status_code}: {response.text}",
                    provider="local",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
            except Exception as exc:
                raise ProviderError(
                    f"Laptop LLM returned invalid JSON: {exc}",
                    provider="local",
                )

            answer = data.get("answer")
            if not answer or not isinstance(answer, str):
                raise ProviderError(
                    f"Laptop LLM response missing valid 'answer' field. Got: {data}",
                    provider="local",
                )

            model_name = data.get("model", "local-transformer")

            return ProviderResponse(
                answer=answer.strip(),
                model=model_name,
                provider="local",
                raw_response=data,
            )
