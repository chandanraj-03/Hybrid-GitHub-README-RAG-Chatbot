import logging
from typing import Dict, Any, List, Optional
from backend.app.rag.pipeline import RagPipeline
from backend.app.providers.base import BaseLLMProvider, ProviderResponse, ProviderError

logger = logging.getLogger("rag_orchestrator")


class RagOrchestrator:
    """
    Multi-Provider Cascading RAG Orchestrator.
    Prioritizes Local Laptop LLM, then cascades through cloud fallbacks
    (Gemini -> Grok -> OpenRouter -> Groq) upon timeouts, rate limits, or errors.
    """

    def __init__(
        self,
        rag_pipeline: RagPipeline,
        providers: List[BaseLLMProvider],
        top_k: int = 4,
    ):
        self.rag_pipeline = rag_pipeline
        self.providers = providers
        self.top_k = top_k

    async def answer_question(
        self,
        question: str,
        conversation: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes hybrid RAG pipeline:
        1. Retrieve top-K README chunks
        2. Iterate through configured LLM provider cascade
        3. First successful provider returns answer with failover trail & sources
        """
        k = top_k or self.top_k

        # Step 1: Retrieve relevant README chunks
        retrieved_chunks, formatted_context, sources = self.rag_pipeline.retrieve(
            query=question,
            top_k=k,
        )

        context_payload = [
            {
                "text": chunk.text,
                "section": chunk.section,
                "heading_level": chunk.heading_level,
                "file": chunk.file,
                "score": chunk.score,
            }
            for chunk in retrieved_chunks
        ]

        failover_trail: List[Dict[str, str]] = []

        # Filter only configured providers
        active_providers = [p for p in self.providers if p.is_configured()]

        if not active_providers:
            raise ProviderError(
                "No LLM providers are configured with valid API keys or endpoints.",
                provider="hybrid",
            )

        # Step 2: Cascade through providers in priority order
        for idx, provider in enumerate(active_providers):
            provider_name = getattr(provider, "name", "unknown")
            is_primary = (idx == 0 and provider_name == "local")

            try:
                logger.info(f"Attempting inference with provider '{provider_name}'...")
                resp: ProviderResponse = await provider.generate(
                    question=question,
                    context_chunks=context_payload,
                    formatted_context=formatted_context,
                    conversation=conversation,
                )

                # If succeeded after previous failures
                has_failover = len(failover_trail) > 0
                primary_fail_reason = failover_trail[0]["reason"] if has_failover else None

                return {
                    "answer": resp.answer,
                    "provider": resp.provider,
                    "model": resp.model,
                    "sources": sources,
                    "failover": has_failover,
                    "failover_reason": primary_fail_reason,
                    "failover_trail": failover_trail,
                    "retrieved_chunks_count": len(retrieved_chunks),
                }

            except (ProviderError, Exception) as exc:
                err_msg = str(exc)
                logger.warning(
                    f"Provider '{provider_name}' failed or rate-limited ({err_msg}). "
                    f"Cascading to next provider in fallback chain."
                )
                failover_trail.append({
                    "provider": provider_name,
                    "reason": err_msg,
                })

        # Step 3: If all providers in cascade failed
        trail_summary = " -> ".join([f"{item['provider']} ({item['reason']})" for item in failover_trail])
        logger.error(f"All LLM providers in fallback cascade failed: {trail_summary}")
        raise ProviderError(
            f"All configured LLM providers failed. Cascade trail: {trail_summary}",
            provider="hybrid",
        )
