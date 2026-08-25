import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.providers.base import ProviderResponse, ProviderError
from backend.app.providers.local import LocalLaptopProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.providers.grok import GrokProvider
from backend.app.providers.openrouter import OpenRouterProvider
from backend.app.providers.groq import GroqProvider
from backend.app.services.orchestrator import RagOrchestrator
from backend.app.rag.retriever import RetrievedChunk


@pytest.fixture
def sample_rag_pipeline():
    rag = MagicMock()
    chunk = RetrievedChunk(
        text="## Installation\n\npip install test-project",
        section="Installation",
        heading_level=2,
        file="README.md",
        repository="owner/repo",
        branch="main",
        score=0.9,
    )
    rag.retrieve.return_value = ([chunk], "README CONTEXT:\nInstallation chunk", [{"file": "README.md", "section": "Installation"}])
    return rag


@pytest.mark.asyncio
class TestMultiProviderCascade:

    async def test_laptop_offline_gemini_429_grok_succeeds(self, sample_rag_pipeline):
        # 1. Laptop fails (offline)
        laptop_p = MagicMock(spec=LocalLaptopProvider)
        laptop_p.name = "local"
        laptop_p.is_configured.return_value = True
        laptop_p.generate = AsyncMock(side_effect=ProviderError("Connection refused to laptop", provider="local"))

        # 2. Gemini fails (429 Rate Limit / Quota Exceeded)
        gemini_p = MagicMock(spec=GeminiProvider)
        gemini_p.name = "gemini"
        gemini_p.is_configured.return_value = True
        gemini_p.generate = AsyncMock(side_effect=ProviderError("429 Resource Exhausted / Quota Exceeded", provider="gemini"))

        # 3. Grok succeeds!
        grok_p = MagicMock(spec=GrokProvider)
        grok_p.name = "grok"
        grok_p.is_configured.return_value = True
        grok_p.generate = AsyncMock(return_value=ProviderResponse(
            answer="Grok grounded response: Run pip install test-project",
            model="grok-2-latest",
            provider="grok",
        ))

        openrouter_p = MagicMock(spec=OpenRouterProvider)
        openrouter_p.name = "openrouter"
        openrouter_p.is_configured.return_value = True
        openrouter_p.generate = AsyncMock()

        orchestrator = RagOrchestrator(
            rag_pipeline=sample_rag_pipeline,
            providers=[laptop_p, gemini_p, grok_p, openrouter_p],
        )

        res = await orchestrator.answer_question("How do I install?")

        assert res["provider"] == "grok"
        assert res["model"] == "grok-2-latest"
        assert res["failover"] is True
        assert "Connection refused" in res["failover_reason"]
        assert len(res["failover_trail"]) == 2
        assert res["failover_trail"][0]["provider"] == "local"
        assert res["failover_trail"][1]["provider"] == "gemini"
        assert "Quota Exceeded" in res["failover_trail"][1]["reason"]
        assert "Grok grounded response" in res["answer"]

        laptop_p.generate.assert_called_once()
        gemini_p.generate.assert_called_once()
        grok_p.generate.assert_called_once()
        openrouter_p.generate.assert_not_called()

    async def test_grok_fails_openrouter_succeeds(self, sample_rag_pipeline):
        laptop_p = MagicMock(spec=LocalLaptopProvider)
        laptop_p.name = "local"
        laptop_p.is_configured.return_value = False  # Laptop disabled/unconfigured

        gemini_p = MagicMock(spec=GeminiProvider)
        gemini_p.name = "gemini"
        gemini_p.is_configured.return_value = True
        gemini_p.generate = AsyncMock(side_effect=ProviderError("Rate limit", provider="gemini"))

        grok_p = MagicMock(spec=GrokProvider)
        grok_p.name = "grok"
        grok_p.is_configured.return_value = True
        grok_p.generate = AsyncMock(side_effect=ProviderError("500 Internal Error", provider="grok"))

        openrouter_p = MagicMock(spec=OpenRouterProvider)
        openrouter_p.name = "openrouter"
        openrouter_p.is_configured.return_value = True
        openrouter_p.generate = AsyncMock(return_value=ProviderResponse(
            answer="OpenRouter answer via Llama 3.3",
            model="meta-llama/llama-3.3-70b-instruct",
            provider="openrouter",
        ))

        orchestrator = RagOrchestrator(
            rag_pipeline=sample_rag_pipeline,
            providers=[laptop_p, gemini_p, grok_p, openrouter_p],
        )

        res = await orchestrator.answer_question("How do I install?")
        assert res["provider"] == "openrouter"
        assert res["model"] == "meta-llama/llama-3.3-70b-instruct"
        assert res["failover"] is True
        assert len(res["failover_trail"]) == 2  # gemini, grok
        assert "OpenRouter answer" in res["answer"]

    async def test_groq_final_fallback_succeeds(self, sample_rag_pipeline):
        groq_p = MagicMock(spec=GroqProvider)
        groq_p.name = "groq"
        groq_p.is_configured.return_value = True
        groq_p.generate = AsyncMock(return_value=ProviderResponse(
            answer="Groq ultra-fast response",
            model="llama-3.3-70b-versatile",
            provider="groq",
        ))

        orchestrator = RagOrchestrator(
            rag_pipeline=sample_rag_pipeline,
            providers=[groq_p],
        )

        res = await orchestrator.answer_question("How to run?")
        assert res["provider"] == "groq"
        assert "Groq ultra-fast" in res["answer"]

    async def test_all_cascade_providers_fail_raises_exception(self, sample_rag_pipeline):
        gemini_p = MagicMock(spec=GeminiProvider)
        gemini_p.name = "gemini"
        gemini_p.is_configured.return_value = True
        gemini_p.generate = AsyncMock(side_effect=ProviderError("Gemini Quota Exceeded", provider="gemini"))

        grok_p = MagicMock(spec=GrokProvider)
        grok_p.name = "grok"
        grok_p.is_configured.return_value = True
        grok_p.generate = AsyncMock(side_effect=ProviderError("Grok Quota Exceeded", provider="grok"))

        orchestrator = RagOrchestrator(
            rag_pipeline=sample_rag_pipeline,
            providers=[gemini_p, grok_p],
        )

        with pytest.raises(ProviderError) as exc_info:
            await orchestrator.answer_question("Install?")

        assert "All configured LLM providers failed" in str(exc_info.value)
        assert "Gemini Quota Exceeded" in str(exc_info.value)
        assert "Grok Quota Exceeded" in str(exc_info.value)
