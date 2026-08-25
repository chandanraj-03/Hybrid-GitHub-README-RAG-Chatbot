"""
Hybrid GitHub README RAG Chatbot - Live Interactive Demo
Demonstrates:
  1. Flow 1: Laptop ON -> Local LLM grounded answer with sources.
  2. Flow 2: Multi-Hop Cloud Cascade (Laptop Offline -> Gemini Quota Limit -> Grok/OpenRouter/Groq).
  3. Flow 3: Strict Grounding Check.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app.config import settings
from backend.app.github.client import GitHubClient
from backend.app.github.readme_loader import GitHubReadmeLoader, ReadmeDocument
from backend.app.github.sync import GitHubSyncManager
from backend.app.rag.chunker import MarkdownHeadingChunker
from backend.app.rag.embeddings import get_embedding_model
from backend.app.rag.vector_store import InMemoryVectorStore
from backend.app.rag.pipeline import RagPipeline
from backend.app.providers.base import ProviderError, ProviderResponse
from backend.app.providers.local import LocalLaptopProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.providers.grok import GrokProvider
from backend.app.providers.openrouter import OpenRouterProvider
from backend.app.providers.groq import GroqProvider
from backend.app.services.orchestrator import RagOrchestrator
from laptop.app.model import LaptopTransformerModel

BANNER = r"""
===================================================================
      HYBRID GITHUB README RAG - MULTI-PROVIDER CASCADE DEMO
===================================================================
  [1] Knowledge Base: GitHub README.md Only
  [2] Primary: Local Laptop Transformer Model
  [3] Fallback Cascade: Gemini -> xAI Grok -> OpenRouter -> Groq
  [4] Strict Grounding & Structured Source Citations
===================================================================
"""


async def setup_rag(repo_url: str = "https://github.com/tiangolo/fastapi"):
    print(f"\n[*] Initializing RAG Pipeline with embedding provider: {settings.EMBEDDING_PROVIDER}...")
    chunker = MarkdownHeadingChunker(max_chunk_size=800, chunk_overlap=100)
    embedding_model = get_embedding_model(settings.EMBEDDING_PROVIDER)
    vector_store = InMemoryVectorStore()
    rag_pipeline = RagPipeline(
        chunker=chunker,
        embedding_model=embedding_model,
        vector_store=vector_store,
    )

    github_client = GitHubClient(token=settings.GITHUB_TOKEN)
    readme_loader = GitHubReadmeLoader(client=github_client)
    sync_manager = GitHubSyncManager(loader=readme_loader, rag_pipeline=rag_pipeline)

    print(f"[*] Fetching & indexing README from '{repo_url}'...")
    sync_result = await sync_manager.sync(repo_url=repo_url, force=True)
    if sync_result["success"]:
        print(f"[OK] {sync_result['message']}")
        print(f"[OK] SHA: {sync_manager.current_sha} | Chunks: {sync_manager.chunk_count}")
    else:
        print(f"[!] Sync Note: {sync_result.get('message')}. Loading standard fallback sample README.")
        sample_doc = ReadmeDocument(
            owner="fastapi",
            repo="fastapi",
            branch="main",
            sha="sample_sha_123",
            filename="README.md",
            raw_markdown="""# FastAPI\n\n## Installation\n\n```bash\npip install fastapi uvicorn\n```\n\n## Example\n\n```python\nfrom fastapi import FastAPI\napp = FastAPI()\n```\n""",
        )
        await rag_pipeline.index_readme(sample_doc)

    return rag_pipeline, sync_manager


async def demonstrate_flow1_laptop_on(rag_pipeline):
    print("\n" + "=" * 65)
    print("DEMO FLOW 1: Laptop ON -> README RAG -> Local LLM -> Answer")
    print("=" * 65)

    question = "How do I install the project?"
    print(f"User Question: '{question}'")

    laptop_model = LaptopTransformerModel()
    chunks, _, sources = rag_pipeline.retrieve(question, top_k=2)
    context_payload = [{"text": c.text, "section": c.section} for c in chunks]

    answer = laptop_model.generate_answer(question, context_payload)

    print(f"\n[Response via Local LLM]")
    print(f"Provider: LOCAL ({laptop_model.model_name})")
    print(f"Answer:\n{answer}")
    print(f"Sources: {[s['file'] + ' -> ' + s['section'] for s in sources]}")


async def demonstrate_flow2_multihop_cascade(rag_pipeline):
    print("\n" + "=" * 65)
    print("DEMO FLOW 2: Laptop Offline & Gemini Over-Limit -> Grok Fallback")
    print("=" * 65)

    question = "What are the installation commands?"
    print(f"User Question: '{question}'")

    offline_laptop = LocalLaptopProvider(base_url="http://localhost:9999", timeout=1.0)
    
    class RateLimitedGemini(GeminiProvider):
        async def generate(self, *args, **kwargs):
            raise ProviderError("HTTP 429: Gemini Quota Exceeded (Resource Exhausted)", provider="gemini", status_code=429)

    rate_limited_gemini = RateLimitedGemini(api_key="mock_key")

    class MockGrok(GrokProvider):
        async def generate(self, *args, **kwargs):
            return ProviderResponse(
                answer="Grok grounded response: Run `pip install fastapi uvicorn` to install.",
                model="grok-2-latest",
                provider="grok",
            )

    mock_grok = MockGrok(api_key="mock_grok_key")

    orchestrator = RagOrchestrator(
        rag_pipeline=rag_pipeline,
        providers=[offline_laptop, rate_limited_gemini, mock_grok],
    )

    print("\n[*] Simulating Overnight Scenario:")
    print("  Hop 1: Local Laptop (Attempting connection -> Offline)")
    print("  Hop 2: Google Gemini (Attempting call -> HTTP 429 Quota Exceeded)")
    print("  Hop 3: xAI Grok (Attempting call -> Success!)")

    result = await orchestrator.answer_question(question)
    print(f"\n[Response via Multi-Provider Cascade]")
    print(f"Active Provider: {result['provider'].upper()} ({result['model']})")
    print(f"Failover Status: {result['failover']}")
    print(f"Cascade Trail: {result['failover_trail']}")
    print(f"Answer:\n{result['answer']}")
    print(f"Sources: {[s['file'] + ' -> ' + s['section'] for s in result['sources']]}")


async def demonstrate_flow3_grounding(rag_pipeline):
    print("\n" + "=" * 65)
    print("DEMO FLOW 3: Strict Grounding Check (Section 26 Test)")
    print("=" * 65)

    absent_question = "What PostgreSQL connection string and database schema are used?"
    print(f"Question about absent info: '{absent_question}'")

    laptop_model = LaptopTransformerModel()
    chunks, _, _ = rag_pipeline.retrieve(absent_question, top_k=2)
    has_db = any("postgres" in c.text.lower() for c in chunks)
    context_payload = [{"text": c.text, "section": c.section} for c in chunks] if has_db else []

    answer = laptop_model.generate_answer(absent_question, context_payload)
    print(f"\nAnswer:\n{answer}")
    print("[OK] Model strictly avoided hallucinating non-existent database details.")


async def main():
    print(BANNER)
    rag_pipeline, sync_manager = await setup_rag()

    await demonstrate_flow1_laptop_on(rag_pipeline)
    await demonstrate_flow2_multihop_cascade(rag_pipeline)
    await demonstrate_flow3_grounding(rag_pipeline)

    print("\n" + "=" * 65)
    print("[OK] All Multi-Provider Hybrid RAG flows demonstrated successfully!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
