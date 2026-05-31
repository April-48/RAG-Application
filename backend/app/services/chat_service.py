"""Chat / Q&A for a single document — the main RAG user flow.

Rough order: check you own the doc -> cache lookup -> retrieve chunks ->
build prompt -> call LLM -> save message + maybe cache the answer.
History is one session per (user, document).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.cache.answer_cache import AnswerCache
from app.core.exceptions import DocumentNotReadyError
from app.models.chunk import DocumentChunk
from app.models.message import Message
from app.rag.embedding_service import Embedder
from app.rag.llm_service import LLM
from app.rag.pipeline import RAGPipeline
from app.rag.prompt_builder import INSUFFICIENT_CONTEXT_MESSAGE
from app.repositories.chat_repository import ChatRepository
from app.services.document_service import DocumentService

# Shape of one cited chunk in sources_json and Redis cache.
Source = dict[str, Any]


# Serialize a chunk to the source shape I store in cache and sources_json.
def _chunk_to_source(chunk: DocumentChunk) -> Source:
    return {
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "chunk_text": chunk.chunk_text,
    }


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
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources_json=sources,
            )
            return answer, sources

        result = self.pipeline.retrieve(document_id, question)
        if result.skip_llm_message:
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=result.skip_llm_message,
                sources_json=[_chunk_to_source(c) for c in result.chunks],
            )
            return result.skip_llm_message, [_chunk_to_source(c) for c in result.chunks]

        if not result.chunks:
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=INSUFFICIENT_CONTEXT_MESSAGE,
                sources_json=[],
            )
            return INSUFFICIENT_CONTEXT_MESSAGE, []

        answer = self.pipeline.generate(question, result)
        sources = [_chunk_to_source(c) for c in result.chunks]

        self.chats.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            sources_json=sources,
        )
        # Only cache real answers, not "insufficient context" style errors.
        self.cache.set(
            user_id=user_id,
            document_id=document_id,
            question=question,
            answer=answer,
            sources=sources,
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
                self.chats.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=result.skip_llm_message,
                    sources_json=[_chunk_to_source(c) for c in result.chunks],
                )
                yield {"type": "token", "data": result.skip_llm_message}
                yield {
                    "type": "sources",
                    "data": [_chunk_to_source(c) for c in result.chunks],
                }
                yield {"type": "done"}
                return

            if not result.chunks:
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

            parts: list[str] = []
            for token in self.pipeline.generate_stream(question, result):
                parts.append(token)
                yield {"type": "token", "data": token}

            answer = "".join(parts).strip()
            sources = [_chunk_to_source(c) for c in result.chunks]
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources_json=sources,
            )
            # Cache write only after we got a full successful stream.
            self.cache.set(
                user_id=user_id,
                document_id=document_id,
                question=question,
                answer=answer,
                sources=sources,
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
