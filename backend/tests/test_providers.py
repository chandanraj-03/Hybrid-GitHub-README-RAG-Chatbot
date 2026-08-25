import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.providers.base import ProviderResponse, ProviderError
from backend.app.providers.local import LocalLaptopProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.services.orchestrator import RagOrchestrator
from backend.app.rag.retriever import RetrievedChunk


@pytest.fixture
def mock_retrieved_chunks():
    chunk = RetrievedChunk(
        text="## Installation\n\nRun pip install test-project",
        section="Installation",
        heading_level=2,
        file="README.md",
        repository="owner/repo",
        branch="main",
        score=0.95,
    )
    return [chunk]


@pytest.fixture
def mock_rag_pipeline(mock_retrieved_chunks):
    rag = MagicMock()
    rag.retrieve.return_value = (
        mock_retrieved_chunks,
        "--- [Context Chunk 1: Section 'Installation'] ---\nRun pip install test-project",
        [{"file": "README.md", "section": "Installation"}],
    )
    return rag


@pytest.mark.asyncio
class TestOrchestratorFailover:

    async def test_laptop_available_returns_local_answer(self, mock_rag_pipeline):
        local_prov = MagicMock(spec=LocalLaptopProvider)
        local_prov.name = "local"
        local_prov.is_configured.return_value = True
        local_prov.generate = AsyncMock(return_value=ProviderResponse(
            answer="Run pip install test-project.",
            model="Qwen2.5-0.5B",
            provider="local",
        ))

        gemini_prov = MagicMock(spec=GeminiProvider)
        gemini_prov.name = "gemini"
        gemini_prov.is_configured.return_value = True
        gemini_prov.generate = AsyncMock()

        orchestrator = RagOrchestrator(
            rag_pipeline=mock_rag_pipeline,
            providers=[local_prov, gemini_prov],
        )

        res = await orchestrator.answer_question("How do I install?")
        assert res["provider"] == "local"
        assert res["model"] == "Qwen2.5-0.5B"
        assert res["failover"] is False
        assert res["failover_reason"] is None
        assert "pip install test-project" in res["answer"]
        assert len(res["sources"]) == 1

        local_prov.generate.assert_called_once()
        gemini_prov.generate.assert_not_called()

    async def test_laptop_unavailable_triggers_gemini_fallback(self, mock_rag_pipeline):
        local_prov = MagicMock(spec=LocalLaptopProvider)
        local_prov.name = "local"
        local_prov.is_configured.return_value = True
        local_prov.generate = AsyncMock(side_effect=ProviderError("Connection refused", provider="local"))

        gemini_prov = MagicMock(spec=GeminiProvider)
        gemini_prov.name = "gemini"
        gemini_prov.is_configured.return_value = True
        gemini_prov.generate = AsyncMock(return_value=ProviderResponse(
            answer="Gemini answer: Run pip install test-project",
            model="gemini-1.5-flash",
            provider="gemini",
        ))

        orchestrator = RagOrchestrator(
            rag_pipeline=mock_rag_pipeline,
            providers=[local_prov, gemini_prov],
        )

        res = await orchestrator.answer_question("How do I install?")
        assert res["provider"] == "gemini"
        assert res["model"] == "gemini-1.5-flash"
        assert res["failover"] is True
        assert "Connection refused" in res["failover_reason"]
        assert "Gemini answer" in res["answer"]

        local_prov.generate.assert_called_once()
        gemini_prov.generate.assert_called_once()

    async def test_laptop_timeout_triggers_gemini_fallback(self, mock_rag_pipeline):
        local_prov = MagicMock(spec=LocalLaptopProvider)
        local_prov.name = "local"
        local_prov.is_configured.return_value = True
        local_prov.generate = AsyncMock(side_effect=ProviderError("Request timed out after 4.0s", provider="local"))

        gemini_prov = MagicMock(spec=GeminiProvider)
        gemini_prov.name = "gemini"
        gemini_prov.is_configured.return_value = True
        gemini_prov.generate = AsyncMock(return_value=ProviderResponse(
            answer="Gemini fallback answer",
            model="gemini-1.5-flash",
            provider="gemini",
        ))

        orchestrator = RagOrchestrator(
            rag_pipeline=mock_rag_pipeline,
            providers=[local_prov, gemini_prov],
        )

        res = await orchestrator.answer_question("How do I install?")
        assert res["provider"] == "gemini"
        assert res["failover"] is True
        assert "timed out" in res["failover_reason"]

    async def test_laptop_http_500_triggers_gemini_fallback(self, mock_rag_pipeline):
        local_prov = MagicMock(spec=LocalLaptopProvider)
        local_prov.name = "local"
        local_prov.is_configured.return_value = True
        local_prov.generate = AsyncMock(side_effect=ProviderError("HTTP 500 Internal Server Error", provider="local"))

        gemini_prov = MagicMock(spec=GeminiProvider)
        gemini_prov.name = "gemini"
        gemini_prov.is_configured.return_value = True
        gemini_prov.generate = AsyncMock(return_value=ProviderResponse(
            answer="Gemini fallback answer",
            model="gemini-1.5-flash",
            provider="gemini",
        ))

        orchestrator = RagOrchestrator(
            rag_pipeline=mock_rag_pipeline,
            providers=[local_prov, gemini_prov],
        )

        res = await orchestrator.answer_question("How do I install?")
        assert res["provider"] == "gemini"
        assert res["failover"] is True

    async def test_both_providers_fail_raises_exception(self, mock_rag_pipeline):
        local_prov = MagicMock(spec=LocalLaptopProvider)
        local_prov.name = "local"
        local_prov.is_configured.return_value = True
        local_prov.generate = AsyncMock(side_effect=ProviderError("Offline", provider="local"))

        gemini_prov = MagicMock(spec=GeminiProvider)
        gemini_prov.name = "gemini"
        gemini_prov.is_configured.return_value = True
        gemini_prov.generate = AsyncMock(side_effect=ProviderError("Quota exceeded", provider="gemini"))

        orchestrator = RagOrchestrator(
            rag_pipeline=mock_rag_pipeline,
            providers=[local_prov, gemini_prov],
        )

        with pytest.raises(ProviderError) as exc_info:
            await orchestrator.answer_question("How do I install?")

        assert "Quota exceeded" in str(exc_info.value)
