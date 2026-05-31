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


# End-to-end RAG stages: ingest files into chunks, retrieve, generate answers.
class RAGPipeline:

    # Wire embedder, LLM, chunk repo, and retrieval for this DB session.
    def __init__(
        self,
        db: Session,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
    ) -> None:
        self.db = db
        self.embedder = embedder or get_embedding_service()
        self.llm = llm or get_llm_service()
        self.chunks = ChunkRepository(db)
        self.retrieval = RetrievalService(db, embedder=self.embedder)

    # Parse a file, chunk it, embed each chunk, and persist rows.
    # Output: chunk count (0 when no text extracted).
    # Raises on parse/embedding failure so the caller can mark the doc failed.
    def ingest(
        self, *, document_id: uuid.UUID, file_path: str | Path, file_type: str | None
    ) -> int:
        pages = extract_pages(file_path, file_type)
        chunks = split_pages(pages)
        if not chunks:
            return 0

        embeddings = self.embedder.embed_texts([c.chunk_text for c in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        return self.chunks.create_many(document_id, chunks)

    # Route the question and return chunks plus optional direct-answer metadata.
    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        return self.retrieval.retrieve(document_id, question, top_k)

    # Generate a grounded answer from a retrieval result.
    # Returns skip_llm_message, direct_answer, empty string, or LLM output.
    def generate(self, question: str, result: RetrievalResult) -> str:
        if result.skip_llm_message:
            return result.skip_llm_message
        if result.direct_answer is not None:
            return result.direct_answer
        if not result.chunks:
            return ""
        return self.llm.generate(build_messages(question, result.chunks))

    # Stream a grounded answer token-by-token from a retrieval result.
    def generate_stream(
        self, question: str, result: RetrievalResult
    ) -> Iterator[str]:
        if result.skip_llm_message:
            yield result.skip_llm_message
            return
        if result.direct_answer is not None:
            yield result.direct_answer
            return
        if not result.chunks:
            return
        yield from self.llm.generate_stream(build_messages(question, result.chunks))
