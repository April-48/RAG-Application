"""Chat / Q&A for a single document — the main RAG user flow.

Rough order: check you own the doc -> cache lookup -> retrieve chunks ->
build prompt -> call LLM -> save message + maybe cache the answer.
History is one session per (user, document).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.cache.answer_cache import AnswerCache
from app.core.exceptions import DocumentNotReadyError
from app.models.chunk import DocumentChunk
from app.models.message import Message
from app.rag.embedding_service import Embedder
from app.rag.llm_service import LLM
from app.rag.generation import StreamGenerationState
from app.rag.pipeline import GenerationOutput, RAGPipeline
from app.rag.prompt_builder import INSUFFICIENT_CONTEXT_MESSAGE, is_insufficient_context_answer
from app.repositories.chat_repository import ChatRepository
from app.services.document_service import DocumentService

# Shape of one cited chunk in sources_json and Redis cache.
Source = dict[str, Any]

logger = logging.getLogger("app.services.chat_service")


@dataclass(frozen=True)
class ClearHistoryResult:
    """Counts returned by clear_history() so the API can report what was removed.

    deleted — how many message rows were removed from Postgres.
    cache_cleared — how many Redis answer-cache keys were deleted (0 if cache off).
    """

    deleted: int
    cache_cleared: int


def _chunk_to_source(chunk: DocumentChunk) -> Source:
    """Turn one DocumentChunk into the JSON shape shown in the UI and Redis cache.

    Each source has chunk_index, page_number, and chunk_text so the frontend
    can render citation snippets without another DB round trip.
    """
    return {
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "chunk_text": chunk.chunk_text,
    }


def _sources_from_chunks(chunks: list[DocumentChunk]) -> list[Source]:
    """Map a list of chunks to the sources_json format stored on assistant messages."""
    return [_chunk_to_source(chunk) for chunk in chunks]


def _log_answer_summary(
    *,
    document_id: uuid.UUID,
    question: str,
    answer_path: str,
    raw_retrieved_count: int,
    prompt_chunk_count: int,
    display_source_count: int,
    context_chars: int,
) -> None:
    """Write one structured log line after a successful LLM answer.

    Includes answer_path (llm, cache, direct_extraction, …) and chunk counts
    so you can trace a question through retrieval → prompt → response in logs.
    """
    logger.info(
        "Answer summary document_id=%s path=%s question=%r raw_chunks=%s "
        "prompt_chunks=%s display_sources=%s context_chars=%s",
        document_id,
        answer_path,
        question[:120],
        raw_retrieved_count,
        prompt_chunk_count,
        display_source_count,
        context_chars,
    )


# I orchestrate Q&A: access checks, cache, retrieval, LLM, and chat history.
class ChatService:

    # Wire document service, RAG pipeline, chat repo, and optional Redis cache.
    def __init__(
        self,
        db: Session,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
        pipeline: RAGPipeline | None = None,
        documents: DocumentService | None = None,
        chats: ChatRepository | None = None,
        cache: AnswerCache | None = None,
    ) -> None:
        self.documents = documents or DocumentService(db, embedder=embedder)
        self.pipeline = pipeline or RAGPipeline(db, embedder=embedder, llm=llm)
        self.chats = chats or ChatRepository(db)
        self.cache = cache or AnswerCache()

    # Verify doc access, ensure status is ready, and persist the user question.
    # Returns session id — I do not run retrieval yet so cache hits skip it.
    # Raises DocumentNotReadyError when ingestion has not finished.
    def _begin(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> uuid.UUID:
        document = self.documents.get_accessible_document(document_id, user_id)
        if document.status != "ready":
            raise DocumentNotReadyError()

        session = self.chats.get_or_create_session(
            user_id=user_id, document_id=document_id
        )
        self.chats.add_message(
            session_id=session.id, role="user", content=question
        )
        return session.id

    # Answer one question and return the reply plus source citations.
    # I check Redis before retrieval and LLM to save tokens on repeats.
    def ask(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> tuple[str, list[Source]]:
        session_id = self._begin(
            user_id=user_id, document_id=document_id, question=question
        )

        # Check Redis before we burn tokens on retrieval + LLM.
        cached = self.cache.get(
            user_id=user_id, document_id=document_id, question=question
        )
        if cached is not None:
            answer = cached["answer"]
            sources = cached.get("sources", [])
            logger.info(
                "Answer path=cache document_id=%s question=%r sources=%s",
                document_id,
                question[:120],
                len(sources),
            )
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources_json=sources,
            )
            return answer, sources

        result = self.pipeline.retrieve(document_id, question)
        if result.skip_llm_message:
            skip_sources = _sources_from_chunks(result.chunks)
            logger.info(
                "Answer path=skip_llm document_id=%s route=%s raw_chunks=%s display_sources=%s",
                document_id,
                result.routed.mode.value,
                len(result.chunks),
                len(skip_sources),
            )
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=result.skip_llm_message,
                sources_json=skip_sources,
            )
            return result.skip_llm_message, skip_sources

        if not result.chunks:
            logger.info(
                "Answer path=insufficient_guard document_id=%s route=%s reason=no_chunks "
                "raw_chunks=0 prompt_chunks=0 display_sources=0",
                document_id,
                result.routed.mode.value,
            )
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=INSUFFICIENT_CONTEXT_MESSAGE,
                sources_json=[],
            )
            return INSUFFICIENT_CONTEXT_MESSAGE, []

        output = self.pipeline.generate(
            question, result, document_id=document_id
        )

        if output.answer_path == "direct_extraction":
            answer = output.answer
            sources = _sources_from_chunks(result.chunks)
        elif not output.prompt_chunks:
            logger.info(
                "Answer path=insufficient_guard document_id=%s route=%s reason=no_prompt_chunks "
                "raw_chunks=%s prompt_chunks=0 display_sources=0",
                document_id,
                result.routed.mode.value,
                output.raw_retrieved_count,
            )
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=INSUFFICIENT_CONTEXT_MESSAGE,
                sources_json=[],
            )
            return INSUFFICIENT_CONTEXT_MESSAGE, []

        answer = output.answer
        if not answer.strip():
            logger.info(
                "Answer path=insufficient_guard document_id=%s route=%s reason=empty_llm_output "
                "raw_chunks=%s prompt_chunks=%s display_sources=0",
                document_id,
                result.routed.mode.value,
                output.raw_retrieved_count,
                output.prompt_chunk_count,
            )
            answer = INSUFFICIENT_CONTEXT_MESSAGE
            sources: list[Source] = []
        else:
            sources = _sources_from_chunks(output.prompt_chunks)

        _log_answer_summary(
            document_id=document_id,
            question=question,
            answer_path=output.answer_path,
            raw_retrieved_count=output.raw_retrieved_count,
            prompt_chunk_count=output.prompt_chunk_count,
            display_source_count=len(sources),
            context_chars=output.context_chars,
        )

        self.chats.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            sources_json=sources,
        )
        if not is_insufficient_context_answer(answer):
            self.cache.set(
                user_id=user_id,
                document_id=document_id,
                question=question,
                answer=answer,
                sources=sources,
            )
        elif sources:
            logger.warning(
                "Insufficient-context answer with %s aligned source(s) document_id=%s question=%r",
                len(sources),
                document_id,
                question[:120],
            )
        return answer, sources

    # Stream SSE-style events: token chunks, then sources, then done.
    def ask_stream(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> Iterator[dict[str, Any]]:
        session_id = self._begin(
            user_id=user_id, document_id=document_id, question=question
        )
        cached = self.cache.get(
            user_id=user_id, document_id=document_id, question=question
        )

        # Inner generator for ask_stream.
        # Yields dict events: token chunks, then sources, then done.
        # I use the same event shape for cache hits and live LLM streaming.
        def event_stream() -> Iterator[dict[str, Any]]:
            if cached is not None:
                answer = cached["answer"]
                sources = cached.get("sources", [])
                logger.info(
                    "Answer path=cache document_id=%s question=%r sources=%s",
                    document_id,
                    question[:120],
                    len(sources),
                )
                self.chats.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=answer,
                    sources_json=sources,
                )
                yield {"type": "token", "data": answer}
                yield {"type": "sources", "data": sources}
                yield {"type": "done"}
                return

            result = self.pipeline.retrieve(document_id, question)
            if result.skip_llm_message:
                skip_sources = _sources_from_chunks(result.chunks)
                logger.info(
                    "Answer path=skip_llm document_id=%s route=%s raw_chunks=%s display_sources=%s",
                    document_id,
                    result.routed.mode.value,
                    len(result.chunks),
                    len(skip_sources),
                )
                self.chats.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=result.skip_llm_message,
                    sources_json=skip_sources,
                )
                yield {"type": "token", "data": result.skip_llm_message}
                yield {"type": "sources", "data": skip_sources}
                yield {"type": "done"}
                return

            if not result.chunks:
                logger.info(
                    "Answer path=insufficient_guard document_id=%s route=%s reason=no_chunks "
                    "raw_chunks=0 prompt_chunks=0 display_sources=0",
                    document_id,
                    result.routed.mode.value,
                )
                self.chats.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=INSUFFICIENT_CONTEXT_MESSAGE,
                    sources_json=[],
                )
                yield {"type": "token", "data": INSUFFICIENT_CONTEXT_MESSAGE}
                yield {"type": "sources", "data": []}
                yield {"type": "done"}
                return

            prompt_chunks = self.pipeline.prepare_prompt_chunks(result)
            if not prompt_chunks:
                logger.info(
                    "Answer path=insufficient_guard document_id=%s route=%s reason=no_prompt_chunks "
                    "raw_chunks=%s prompt_chunks=0 display_sources=0",
                    document_id,
                    result.routed.mode.value,
                    len(result.chunks),
                )
                self.chats.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=INSUFFICIENT_CONTEXT_MESSAGE,
                    sources_json=[],
                )
                yield {"type": "token", "data": INSUFFICIENT_CONTEXT_MESSAGE}
                yield {"type": "sources", "data": []}
                yield {"type": "done"}
                return

            stream_state = StreamGenerationState()
            parts: list[str] = []
            for token in self.pipeline.generate_stream(
                question,
                result,
                document_id=document_id,
                state=stream_state,
            ):
                parts.append(token)
                yield {"type": "token", "data": token}

            answer = "".join(parts).strip()
            sources = _sources_from_chunks(prompt_chunks)
            if not answer:
                logger.info(
                    "Answer path=insufficient_guard document_id=%s route=%s reason=empty_llm_output "
                    "raw_chunks=%s prompt_chunks=%s display_sources=0",
                    document_id,
                    result.routed.mode.value,
                    len(result.chunks),
                    len(prompt_chunks),
                )
                answer = INSUFFICIENT_CONTEXT_MESSAGE
                sources = []
                yield {"type": "token", "data": answer}

            _log_answer_summary(
                document_id=document_id,
                question=question,
                answer_path=stream_state.answer_path,
                raw_retrieved_count=len(result.chunks),
                prompt_chunk_count=len(prompt_chunks),
                display_source_count=len(sources),
                context_chars=stream_state.context_chars,
            )

            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources_json=sources,
            )
            if not is_insufficient_context_answer(answer):
                self.cache.set(
                    user_id=user_id,
                    document_id=document_id,
                    question=question,
                    answer=answer,
                    sources=sources,
                )
            elif sources:
                logger.warning(
                    "Insufficient-context answer with %s aligned source(s) document_id=%s question=%r",
                    len(sources),
                    document_id,
                    question[:120],
                )
            yield {"type": "sources", "data": sources}
            yield {"type": "done"}

        return event_stream()

    # Return persisted messages for this user's session on a document.
    # Raises DocumentNotFoundError when the user cannot access the document.
    # Returns an empty list when no conversation exists yet.
    def get_history(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[Message]:
        self.documents.get_accessible_document(document_id, user_id)
        session = self.chats.get_session(
            user_id=user_id, document_id=document_id
        )
        if session is None:
            return []
        return self.chats.list_messages(session.id)

    # Remove all saved messages for this user + document.
    # Also clears Redis answer cache entries for the same pair when cache is on.
    # Raises DocumentNotFoundError when the user cannot access the document.
    def clear_history(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ClearHistoryResult:
        self.documents.get_accessible_document(document_id, user_id)
        session = self.chats.get_session(
            user_id=user_id, document_id=document_id
        )
        deleted = 0
        if session is not None:
            deleted = self.chats.clear_messages(session.id)
        cache_cleared = self.cache.clear_for_document(
            user_id=user_id, document_id=document_id
        )
        return ClearHistoryResult(deleted=deleted, cache_cleared=cache_cleared)
