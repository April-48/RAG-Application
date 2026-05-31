"""RAG pipeline — wires together parse, chunk, embed, retrieve, generate.

Services call RAGPipeline instead of touching each stage directly. Business
stuff (auth, file paths, caching, chat history) stays in services, not here.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.llm_service import LLM, get_llm_service
from app.rag.loader import extract_pages
from app.rag.prompt_builder import build_messages
from app.rag.retrieval_service import RetrievalResult, RetrievalService
from app.rag.text_splitter import split_pages
from app.repositories.chunk_repository import ChunkRepository


class RAGPipeline:
    """End-to-end RAG stages: ingest files into chunks, retrieve, generate answers."""

    def __init__(
        self,
        db: Session,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
    ) -> None:
        """Wire embedder, LLM, chunk repo, and retrieval for this DB session."""
        self.db = db
        self.embedder = embedder or get_embedding_service()
        self.llm = llm or get_llm_service()
        self.chunks = ChunkRepository(db)
        self.retrieval = RetrievalService(db, embedder=self.embedder)

    # --- Ingestion: read file, chunk, embed, save to DB ---
    def ingest(
        self, *, document_id: uuid.UUID, file_path: str | Path, file_type: str | None
    ) -> int:
        """Parse, chunk, embed, and persist a document's chunks.

        Returns the number of chunks stored (0 if no text could be extracted).
        Raises on parse/embedding failures so the caller can mark the document
        ``failed``.
        """
        pages = extract_pages(file_path, file_type)
        chunks = split_pages(pages)
        if not chunks:
            return 0

        embeddings = self.embedder.embed_texts([c.chunk_text for c in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        return self.chunks.create_many(document_id, chunks)

    # --- Q&A: route question, pull chunks, ask the LLM when needed ---
    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        """Return routed chunks (and optional direct answer metadata)."""
        return self.retrieval.retrieve(document_id, question, top_k)

    def generate(self, question: str, result: RetrievalResult) -> str:
        """Generate a grounded answer from a retrieval result."""
        if result.skip_llm_message:
            return result.skip_llm_message
        if result.direct_answer is not None:
            return result.direct_answer
        if not result.chunks:
            return ""
        return self.llm.generate(build_messages(question, result.chunks))

    def generate_stream(
        self, question: str, result: RetrievalResult
    ) -> Iterator[str]:
        """Stream a grounded answer token-by-token."""
        if result.skip_llm_message:
            yield result.skip_llm_message
            return
        if result.direct_answer is not None:
            yield result.direct_answer
            return
        if not result.chunks:
            return
        yield from self.llm.generate_stream(build_messages(question, result.chunks))
