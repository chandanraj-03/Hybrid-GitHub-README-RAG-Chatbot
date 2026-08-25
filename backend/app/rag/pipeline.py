import asyncio
from typing import List, Tuple, Dict, Any, Optional
from backend.app.github.readme_loader import ReadmeDocument
from backend.app.rag.chunker import MarkdownHeadingChunker, TextChunk
from backend.app.rag.embeddings import BaseEmbeddings, get_embedding_model
from backend.app.rag.vector_store import BaseVectorStore, InMemoryVectorStore
from backend.app.rag.retriever import ReadmeRetriever, RetrievedChunk


class RagPipeline:
    """End-to-end RAG pipeline managing chunking, embedding, indexing, and retrieval."""

    def __init__(
        self,
        chunker: Optional[MarkdownHeadingChunker] = None,
        embedding_model: Optional[BaseEmbeddings] = None,
        vector_store: Optional[BaseVectorStore] = None,
        embedding_provider: str = "sentence_transformers",
    ):
        self.chunker = chunker or MarkdownHeadingChunker()
        self.embedding_model = embedding_model or get_embedding_model(embedding_provider)
        self.vector_store = vector_store or InMemoryVectorStore()
        self.retriever = ReadmeRetriever(self.vector_store, self.embedding_model)

    async def index_readme(self, readme_doc: ReadmeDocument) -> int:
        """
        Processes and indexes a ReadmeDocument into the vector store.
        Clears previous index before loading new vectors.
        """
        # Run chunking (CPU-bound) in threadpool if necessary
        chunks: List[TextChunk] = self.chunker.chunk_markdown(
            markdown_text=readme_doc.raw_markdown,
            repository=f"{readme_doc.owner}/{readme_doc.repo}",
            file=readme_doc.filename,
            branch=readme_doc.branch,
        )

        if not chunks:
            self.vector_store.clear()
            return 0

        # Extract raw texts for embedding
        texts = [chunk.text for chunk in chunks]

        # Generate embeddings
        embeddings = await asyncio.to_thread(self.embedding_model.embed_documents, texts)

        # Clear existing vectors and insert new ones
        self.vector_store.clear()
        self.vector_store.add_chunks(chunks, embeddings)

        return len(chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 4,
    ) -> Tuple[List[RetrievedChunk], str, List[Dict[str, str]]]:
        """
        Retrieves top-k relevant chunks for a question.
        Returns (chunks, formatted_context_string, structured_sources).
        """
        chunks = self.retriever.retrieve(query=query, top_k=top_k)
        formatted_context = self.retriever.format_context_for_prompt(chunks)
        sources = self.retriever.extract_sources(chunks)
        return chunks, formatted_context, sources

    def count(self) -> int:
        return self.vector_store.count()
