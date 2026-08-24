from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from indexer.config import IndexerConfig
from indexer.markdown_chunker import MarkdownChunk


class SupabaseUploader:
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.url = supabase_url or IndexerConfig.SUPABASE_URL
        self.key = supabase_key or IndexerConfig.SUPABASE_SERVICE_ROLE_KEY

        if not self.url or not self.key:
            raise ValueError(
                "Supabase URL and Service Role Key are required. "
                "Please configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env file."
            )

        from supabase import create_client
        self.client = create_client(self.url, self.key)

    def get_project_by_github(self, github_url: str) -> Optional[Dict[str, Any]]:
        """Queries the projects table for an existing repository record."""
        resp = (
            self.client.table("projects")
            .select("*")
            .eq("github_url", github_url)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None

    def should_reindex(
        self,
        existing_project: Optional[Dict[str, Any]],
        new_hash: str,
        embedding_model: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """
        Determines whether the project should be indexed or re-indexed.
        
        Returns:
            Tuple of (should_reindex: bool, reason_message: str)
        """
        if existing_project is None:
            return True, "New project. Initial indexing required."

        if force:
            return True, "Force re-indexing flag (--force) specified."

        old_hash = existing_project.get("readme_hash")
        old_model = existing_project.get("embedding_model")

        if old_hash != new_hash:
            return True, f"README content changed (old hash: {old_hash[:8]}... vs new hash: {new_hash[:8]}...)."

        if old_model != embedding_model:
            return True, f"Embedding model changed from '{old_model}' to '{embedding_model}'."

        return False, "README has not changed and embedding model matches. No re-indexing required."

    def upsert_project(
        self,
        github_url: str,
        owner: str,
        repo_name: str,
        readme_hash: str,
        readme_url: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> str:
        """
        Creates or updates a project record in Supabase.
        
        Returns:
            The project UUID.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if project exists
        existing = self.get_project_by_github(github_url)
        
        data = {
            "github_url": github_url,
            "owner": owner,
            "repo_name": repo_name,
            "readme_hash": readme_hash,
            "readme_url": readme_url,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "indexed_at": now,
            "updated_at": now,
        }

        if existing:
            project_id = existing["id"]
            self.client.table("projects").update(data).eq("id", project_id).execute()
            return project_id
        else:
            resp = self.client.table("projects").insert(data).execute()
            if resp.data and len(resp.data) > 0:
                return resp.data[0]["id"]
            raise RuntimeError(f"Failed to create project record in Supabase: {resp}")

    def delete_project_chunks(self, project_id: str) -> None:
        """Deletes all existing chunks for a project."""
        self.client.table("readme_chunks").delete().eq("project_id", project_id).execute()

    def upload_chunks(
        self,
        project_id: str,
        chunks: List[MarkdownChunk],
        embeddings: List[List[float]],
        batch_size: int = 50,
    ) -> int:
        """
        Uploads chunks and their vector embeddings to the readme_chunks table in batches.
        
        Returns:
            Total count of successfully uploaded chunks.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch between number of chunks ({len(chunks)}) and embeddings ({len(embeddings)})"
            )

        records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            records.append({
                "project_id": project_id,
                "chunk_index": chunk.chunk_index,
                "section_title": chunk.section_title,
                "section_path": chunk.section_path,
                "content": chunk.content,
                "embedding": embedding,
            })

        # Batch insert
        uploaded = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            resp = self.client.table("readme_chunks").insert(batch).execute()
            uploaded += len(batch)

        return uploaded
