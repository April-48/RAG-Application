"""Shared helpers for RAG generation — chunk filtering, logging, LLM calls."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator

from app.models.chunk import DocumentChunk
from app.rag.llm_service import LLM
from app.rag.prompt_builder import (
    build_messages,
    context_length_in_messages,
    filter_usable_chunks,
    is_insufficient_context_answer,
    log_prompt_context,
)
from app.rag.retrieval_service import RetrievalResult

logger = logging.getLogger("app.rag.generation")


# Filter unusable chunks; return None when nothing remains for LLM generation.
def prepare_llm_chunks(result: RetrievalResult) -> list[DocumentChunk] | None:
    usable = filter_usable_chunks(result.chunks)
    if usable:
        return usable
    if result.chunks:
        logger.info(
            "Retrieval returned %s chunk(s) but none passed usable-text filter",
            len(result.chunks),
        )
    return None


# Call the LLM with logging and warn when insufficient-context conflicts with chunks.
def generate_answer(
    llm: LLM,
    *,
    document_id: uuid.UUID,
    question: str,
    result: RetrievalResult,
    chunks: list[DocumentChunk],
) -> str:
    messages = build_messages(question, chunks)
    log_prompt_context(
        document_id=str(document_id),
        question=question,
        route=result.routed.mode.value,
        chunks=chunks,
        messages=messages,
    )
    answer = llm.generate(messages)
    context_len = context_length_in_messages(messages)
    if is_insufficient_context_answer(answer) and chunks:
        logger.warning(
            "LLM insufficient-context despite %s chunks (context_chars=%s) "
            "document_id=%s question=%r",
            len(chunks),
            context_len,
            document_id,
            question[:120],
        )
    else:
        logger.info(
            "LLM answer document_id=%s route=%s context_chars=%s answer_chars=%s",
            document_id,
            result.routed.mode.value,
            context_len,
            len(answer),
        )
    return answer


# Stream tokens from the LLM with the same logging as generate_answer.
def generate_answer_stream(
    llm: LLM,
    *,
    document_id: uuid.UUID,
    question: str,
    result: RetrievalResult,
    chunks: list[DocumentChunk],
) -> Iterator[str]:
    messages = build_messages(question, chunks)
    log_prompt_context(
        document_id=str(document_id),
        question=question,
        route=result.routed.mode.value,
        chunks=chunks,
        messages=messages,
    )
    parts: list[str] = []
    for token in llm.generate_stream(messages):
        parts.append(token)
        yield token

    answer = "".join(parts).strip()
    context_len = context_length_in_messages(messages)
    if is_insufficient_context_answer(answer) and chunks:
        logger.warning(
            "LLM insufficient-context despite %s chunks (context_chars=%s) "
            "document_id=%s question=%r",
            len(chunks),
            context_len,
            document_id,
            question[:120],
        )
    else:
        logger.info(
            "LLM stream answer document_id=%s route=%s context_chars=%s answer_chars=%s",
            document_id,
            result.routed.mode.value,
            context_len,
            len(answer),
        )
