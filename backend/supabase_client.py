from typing import Optional, Dict, Any, List
from backend.config import BackendConfig


class SupabaseService:
    _instance: Optional["SupabaseService"] = None

    def __init__(self):
        url = BackendConfig.SUPABASE_URL
        key = BackendConfig.get_supabase_key()
        self.client = None
        
        if url and key:
            try:
                from supabase import create_client
                self.client = create_client(url, key)
            except Exception as e:
                self.client = None

    @classmethod
    def get_instance(cls) -> "SupabaseService":
        if cls._instance is None or cls._instance.client is None:
            cls._instance = cls()
        return cls._instance

    def list_projects(self) -> List[Dict[str, Any]]:
        """Fetches all indexed projects ordered by most recently indexed."""
        if not self.client:
            return []

        resp = (
            self.client.table("projects")
            .select("*")
            .order("indexed_at", desc=True)
            .limit(50)
            .execute()
        )
        return resp.data or []

    def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Fetches project metadata by UUID."""
        if not self.client:
            raise RuntimeError("Supabase client is not configured.")

        resp = (
            self.client.table("projects")
            .select("*")
            .eq("id", project_id)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None

    def get_chunk_count(self, project_id: str) -> int:
        """Returns the total number of chunks for a project."""
        if not self.client:
            return 0

        resp = (
            self.client.table("readme_chunks")
            .select("id", count="exact")
            .eq("project_id", project_id)
            .execute()
        )
        return resp.count if resp.count is not None else len(resp.data or [])

    def search_chunks(
        self,
        project_id: str,
        query_embedding: List[float],
        match_count: int = 5,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Calls the PostgreSQL match_readme_chunks RPC function.
        Strictly isolates retrieval to the provided project_id.
        """
        if not self.client:
            raise RuntimeError("Supabase client is not configured.")

        params = {
            "query_embedding": query_embedding,
            "match_project_id": project_id,
            "match_count": match_count,
            "similarity_threshold": similarity_threshold,
        }

        resp = self.client.rpc("match_readme_chunks", params).execute()
        return resp.data or []
