import time
from typing import Dict, Any
from backend.app.providers.local import LocalLaptopProvider


class LaptopHealthService:
    """Service to monitor laptop LLM server availability and latency."""

    def __init__(self, local_provider: LocalLaptopProvider):
        self.local_provider = local_provider

    async def get_status(self) -> Dict[str, Any]:
        start = time.perf_counter()
        health_info = await self.local_provider.check_health()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "online": health_info.get("online", False),
            "url": self.local_provider.base_url,
            "latency_ms": elapsed_ms if health_info.get("online") else None,
            "details": health_info.get("details"),
            "error": health_info.get("error"),
        }
