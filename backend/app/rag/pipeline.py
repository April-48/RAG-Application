"""RAG pipeline — wires together parse, chunk, embed, retrieve, generate.

Services call RAGPipeline instead of touching each stage directly. Business
stuff (auth, file paths, caching, chat history) stays in services, not here.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.generation import (
    StreamGenerationState,
    generate_answer,
    generate_answer_stream,
    prepare_llm_chunks,
)
from app.rag.llm_service import LLM, get_llm_service
from app.rag.loader import extract_pages
from app.rag.retrieval_service import RetrievalResult, RetrievalService
from app.rag.text_splitter import split_pages
from app.repositories.chunk_repository import ChunkRepository

logger = logging.getLogger("app.rag.pipeline")


@dataclass(frozen=True)
class GenerationOutput:
    """Everything RAGPipeline.generate() returns to ChatService.

    answer — final text shown to the user.
    prompt_chunks — chunks actually sent to the LLM (empty for direct/skip paths).
    answer_path — how the answer was produced: llm, llm_retry, direct_extraction,
      skip_llm, insufficient_guard, etc. Used in logs for debugging.
    raw_retrieved_count — chunks retrieval returned before generation filters.
    prompt_chunk_count — len(prompt_chunks).
    context_chars — character length of document context in the LLM prompt.
    """

    answer: str
    prompt_chunks: list[DocumentChunk]
    answer_path: str
    raw_retrieved_count: int
    prompt_chunk_count: int
    context_chars: int


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
        count = self.chunks.create_many(document_id, chunks)
        logger.info(
            "Ingested document_id=%s chunks=%s embedding_provider=%s",
            document_id,
            count,
            type(self.embedder).__name__,
        )
        return count

    # Route the question and return chunks plus optional direct-answer metadata.
    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        return self.retrieval.retrieve(document_id, question, top_k)

    # Chunks that would be passed to the LLM for this retrieval result (may be None).
    def prepare_prompt_chunks(
        self, result: RetrievalResult
    ) -> list[DocumentChunk] | None:
        prep = prepare_llm_chunks(result)
        return prep.prompt_chunks if prep else None

    # Generate a grounded answer from a retrieval result.
    def generate(
        self,
        question: str,
        result: RetrievalResult,
        *,
        document_id: uuid.UUID | None = None,
    ) -> GenerationOutput:
        raw_count = len(result.chunks)

        if result.skip_llm_message:
            logger.info(
                "Answer path=skip_llm route=%s message=%r raw_chunks=%s",
                result.routed.mode.value,
                result.skip_llm_message[:80],
                raw_count,
            )
            return GenerationOutput(
                answer=result.skip_llm_message,
                prompt_chunks=[],
                answer_path="skip_llm",
                raw_retrieved_count=raw_count,
                prompt_chunk_count=0,
                context_chars=0,
            )

        if result.direct_answer is not None:
            logger.info(
                "Answer path=direct_extraction route=%s raw_chunks=%s",
                result.routed.mode.value,
                raw_count,
            )
            return GenerationOutput(
                answer=result.direct_answer,
                prompt_chunks=[],
                answer_path="direct_extraction",
                raw_retrieved_count=raw_count,
                prompt_chunk_count=0,
                context_chars=0,
            )

        prep = prepare_llm_chunks(result)
        if prep is None:
            logger.info(
                "Answer path=insufficient_guard route=%s reason=no_usable_chunks raw_chunks=%s",
                result.routed.mode.value,
                raw_count,
            )
            return GenerationOutput(
                answer="",
                prompt_chunks=[],
                answer_path="insufficient_guard",
                raw_retrieved_count=raw_count,
                prompt_chunk_count=0,
                context_chars=0,
            )

        doc_id = document_id or _document_id_from_chunks(prep.prompt_chunks)
        answer, answer_path, context_chars = generate_answer(
            self.llm,
            document_id=doc_id,
            question=question,
            result=result,
            chunks=prep.prompt_chunks,
        )
        return GenerationOutput(
            answer=answer,
            prompt_chunks=prep.prompt_chunks,
            answer_path=answer_path,
            raw_retrieved_count=prep.raw_retrieved_count,
            prompt_chunk_count=len(prep.prompt_chunks),
            context_chars=context_chars,
        )

    # Stream a grounded answer token-by-token from a retrieval result.
    def generate_stream(
        self,
        question: str,
        result: RetrievalResult,
        *,
        document_id: uuid.UUID | None = None,
        state: StreamGenerationState | None = None,
    ) -> Iterator[str]:
        if result.skip_llm_message:
            logger.info(
                "Answer path=skip_llm route=%s message=%r",
                result.routed.mode.value,
                result.skip_llm_message[:80],
            )
            if state is not None:
                state.answer_path = "skip_llm"
                state.context_chars = 0
            yield result.skip_llm_message
            return

        if result.direct_answer is not None:
            logger.info(
                "Answer path=direct_extraction route=%s",
                result.routed.mode.value,
            )
            if state is not None:
                state.answer_path = "direct_extraction"
                state.context_chars = 0
            yield result.direct_answer
            return

        prep = prepare_llm_chunks(result)
        if prep is None:
            logger.info(
                "Answer path=insufficient_guard route=%s reason=no_usable_chunks raw_chunks=%s",
                result.routed.mode.value,
                len(result.chunks),
            )
            if state is not None:
                state.answer_path = "insufficient_guard"
                state.context_chars = 0
            return

        doc_id = document_id or _document_id_from_chunks(prep.prompt_chunks)
        yield from generate_answer_stream(
            self.llm,
            document_id=doc_id,
            question=question,
            result=result,
            chunks=prep.prompt_chunks,
            state=state,
        )


def _document_id_from_chunks(chunks: list[DocumentChunk]) -> uuid.UUID:
    """Read document_id from the first prompt chunk when caller did not pass one."""
    return chunks[0].document_id
