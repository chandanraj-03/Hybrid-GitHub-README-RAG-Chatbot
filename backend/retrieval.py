"""
Retrieval Module for Chatbot Backend.
Executes project-isolated vector search via Supabase pgvector and formats context.
"""

from typing import List, Tuple

try:
    from backend.config import BackendConfig
    from backend.schemas import SourceItem
    from backend.supabase_client import SupabaseService
except ImportError:
    from config import BackendConfig
    from schemas import SourceItem
    from supabase_client import SupabaseService


class ReadmeRetriever:
    def __init__(self, supabase_service: SupabaseService):
        self.supabase_service = supabase_service

    def retrieve(
        self,
        project_id: str,
        question_embedding: List[float],
        top_k: int = None,
        similarity_threshold: float = None,
    ) -> Tuple[List[SourceItem], str]:
        """
        Retrieves top relevant README chunks for a given project and query embedding.
        
        Returns:
            Tuple of:
              - List of SourceItem objects
              - Concatenated context string for LLM generation
        """
        k = top_k if top_k is not None else BackendConfig.TOP_K
        threshold = similarity_threshold if similarity_threshold is not None else BackendConfig.SIMILARITY_THRESHOLD

        raw_results = self.supabase_service.search_chunks(
            project_id=project_id,
            query_embedding=question_embedding,
            match_count=k,
            similarity_threshold=threshold,
        )

        sources: List[SourceItem] = []
        context_parts: List[str] = []

        for item in raw_results:
            score = float(item.get("similarity", 0.0))
            # Double-check threshold filter
            if score < threshold:
                continue

            sec_title = item.get("section_title") or "General"
            sec_path = item.get("section_path") or sec_title
            content = (item.get("content") or "").strip()
            chunk_idx = item.get("chunk_index")

            sources.append(SourceItem(
                chunk_index=chunk_idx,
                section=sec_title,
                section_path=sec_path,
                content=content,
                score=round(score, 4),
            ))

            # Format for LLM prompt context
            context_parts.append(f"### Section: {sec_path}\n{content}")

        formatted_context = "\n\n".join(context_parts).strip()
        return sources, formatted_context
