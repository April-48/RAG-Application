"""Shared helpers for the generation ("G") step in RAG.

After retrieval returns chunks, this module:
  1. Filters out boilerplate and tiny chunks (prepare_llm_chunks)
  2. Builds the prompt and calls the LLM (generate_answer / generate_answer_stream)
  3. Retries once if the model refuses with "insufficient context" too eagerly

RAGPipeline and ChatService call these functions — they do not talk to the LLM
directly. That keeps prompt logic in prompt_builder and LLM wiring in llm_service.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from app.models.chunk import DocumentChunk
from app.rag.llm_service import LLM
from app.rag.prompt_builder import (
    build_messages,
    build_retry_messages,
    context_length_in_messages,
    filter_usable_chunks,
    is_insufficient_context_answer,
    is_obvious_boilerplate_chunk,
    log_prompt_context,
    MIN_CONTEXT_CHARS_FOR_RETRY,
)
from app.rag.retrieval_service import RetrievalResult

logger = logging.getLogger("app.rag.generation")


@dataclass(frozen=True)
class PromptChunkPrep:
    """Result of prepare_llm_chunks — what actually goes into the LLM prompt.

    raw_retrieved_count — how many chunks retrieval returned before filtering.
    prompt_chunks — the list that build_messages() will format into context.
    removed_by_boilerplate — how many chunks I dropped as obvious noise.
    """

    raw_retrieved_count: int
    prompt_chunks: list[DocumentChunk]
    removed_by_boilerplate: int


@dataclass
class StreamGenerationState:
    """Filled in by generate_answer_stream so ChatService can log the final path.

    answer_path — "llm", "llm_retry", etc. Same values as non-streaming generate.
    context_chars — total character length of document context in the prompt.
    """

    answer_path: str = "llm"
    context_chars: int = 0


def prepare_llm_chunks(result: RetrievalResult) -> PromptChunkPrep | None:
    """Filter retrieval chunks before they go to the LLM.

    Two passes:
      1. filter_usable_chunks — drop chunks shorter than MIN_USABLE_CHUNK_CHARS
      2. is_obvious_boilerplate_chunk — drop conference/copyright noise

    Safety net: if every length-ok chunk looks like boilerplate, I keep them anyway
    so the LLM at least has something to read.

    Returns None when nothing usable remains — caller should show insufficient-context.
    """
    raw_count = len(result.chunks)
    length_ok = filter_usable_chunks(result.chunks)
    prompt_chunks = [
        chunk
        for chunk in length_ok
        if not is_obvious_boilerplate_chunk(chunk.chunk_text or "")
    ]
    removed = len(length_ok) - len(prompt_chunks)
    if removed:
        logger.info(
            "Generation filter removed %s obvious boilerplate chunk(s) "
            "(raw_retrieved=%s length_ok=%s prompt=%s)",
            removed,
            raw_count,
            len(length_ok),
            len(prompt_chunks),
        )

    if not prompt_chunks and length_ok:
        logger.info(
            "All length-ok chunks looked like boilerplate; keeping %s for LLM (raw=%s)",
            len(length_ok),
            raw_count,
        )
        prompt_chunks = length_ok
        removed = 0

    if not prompt_chunks:
        if result.chunks:
            logger.info(
                "Retrieval returned %s chunk(s) but none passed generation filters",
                raw_count,
            )
        return None

    return PromptChunkPrep(
        raw_retrieved_count=raw_count,
        prompt_chunks=prompt_chunks,
        removed_by_boilerplate=removed,
    )


def generate_answer(
    llm: LLM,
    *,
    document_id: uuid.UUID,
    question: str,
    result: RetrievalResult,
    chunks: list[DocumentChunk],
) -> tuple[str, str, int]:
    """Call the LLM once and maybe retry if it refuses too quickly.

    Flow:
      1. build_messages() → llm.generate()
      2. If the answer is the fixed "insufficient context" line AND we sent
         enough context (>= MIN_CONTEXT_CHARS_FOR_RETRY), retry once with a
         softer user instruction (build_retry_messages).
      3. Log whether the final path was llm or llm_retry.

    Returns (answer_text, answer_path, context_chars).
    """
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
    answer_path = "llm"

    if (
        is_insufficient_context_answer(answer)
        and chunks
        and context_len >= MIN_CONTEXT_CHARS_FOR_RETRY
    ):
        logger.info(
            "Retrying LLM once after insufficient-context "
            "(prompt_chunks=%s context_chars=%s document_id=%s)",
            len(chunks),
            context_len,
            document_id,
        )
        retry_messages = build_retry_messages(question, chunks)
        answer = llm.generate(retry_messages)
        context_len = context_length_in_messages(retry_messages)
        answer_path = "llm_retry" if not is_insufficient_context_answer(answer) else "llm"

    if is_insufficient_context_answer(answer) and chunks:
        logger.warning(
            "LLM insufficient-context despite %s prompt chunk(s) (context_chars=%s) "
            "document_id=%s question=%r answer_path=%s",
            len(chunks),
            context_len,
            document_id,
            question[:120],
            answer_path,
        )
    else:
        logger.info(
            "LLM answer document_id=%s route=%s path=%s context_chars=%s answer_chars=%s",
            document_id,
            result.routed.mode.value,
            answer_path,
            context_len,
            len(answer),
        )
    return answer, answer_path, context_len


def generate_answer_stream(
    llm: LLM,
    *,
    document_id: uuid.UUID,
    question: str,
    result: RetrievalResult,
    chunks: list[DocumentChunk],
    state: StreamGenerationState | None = None,
) -> Iterator[str]:
    """Stream LLM tokens to the client, with the same retry logic as generate_answer.

    Streaming is trickier for retries: I buffer the entire first attempt before
    yielding anything. If it looks like an insufficient-context refusal and we
    had enough context, I discard the first attempt and stream the retry instead.

    If the first attempt is fine, I yield the buffered tokens after the check.
    Pass a StreamGenerationState if the caller wants answer_path and context_chars
    after streaming finishes (ChatService uses this for logging).
    """
    messages = build_messages(question, chunks)
    log_prompt_context(
        document_id=str(document_id),
        question=question,
        route=result.routed.mode.value,
        chunks=chunks,
        messages=messages,
    )

    first_parts: list[str] = []
    for token in llm.generate_stream(messages):
        first_parts.append(token)
    first_answer = "".join(first_parts).strip()
    context_len = context_length_in_messages(messages)
    answer_path = "llm"

    if (
        is_insufficient_context_answer(first_answer)
        and chunks
        and context_len >= MIN_CONTEXT_CHARS_FOR_RETRY
    ):
        logger.info(
            "Retrying LLM stream once after insufficient-context "
            "(prompt_chunks=%s context_chars=%s document_id=%s)",
            len(chunks),
            context_len,
            document_id,
        )
        retry_messages = build_retry_messages(question, chunks)
        retry_parts: list[str] = []
        for token in llm.generate_stream(retry_messages):
            retry_parts.append(token)
            yield token
        answer = "".join(retry_parts).strip()
        context_len = context_length_in_messages(retry_messages)
        answer_path = "llm_retry" if not is_insufficient_context_answer(answer) else "llm"
    else:
        for token in first_parts:
            yield token
        answer = first_answer

    if state is not None:
        state.answer_path = answer_path
        state.context_chars = context_len

    if is_insufficient_context_answer(answer) and chunks:
        logger.warning(
            "LLM insufficient-context despite %s prompt chunk(s) (context_chars=%s) "
            "document_id=%s question=%r answer_path=%s",
            len(chunks),
            context_len,
            document_id,
            question[:120],
            answer_path,
        )
    else:
        logger.info(
            "LLM stream answer document_id=%s route=%s path=%s context_chars=%s answer_chars=%s",
            document_id,
            result.routed.mode.value,
            answer_path,
            context_len,
            len(answer),
        )
