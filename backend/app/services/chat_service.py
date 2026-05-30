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


def _chunk_to_source(chunk: DocumentChunk) -> Source:
    """Serialize a chunk to the source shape stored in cache / sources_json."""
    return {
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
        "chunk_text": chunk.chunk_text,
    }


class ChatService:
    """Orchestrates Q&A: access checks, cache, retrieval, LLM, chat history."""

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
        """Wire document service, RAG pipeline, chat repo, and optional Redis cache."""
        self.documents = documents or DocumentService(db, embedder=embedder)
        self.pipeline = pipeline or RAGPipeline(db, embedder=embedder, llm=llm)
        self.chats = chats or ChatRepository(db)
        self.cache = cache or AnswerCache()

    def _begin(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> uuid.UUID:
        """Make sure user can access doc, it's ready, and save their question first.

        Returns session id. Does NOT run retrieval yet — cache hit can skip that entirely.
        """
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

    def ask(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> tuple[str, list[Source]]:
        """One-shot answer + sources — checks cache before retrieval/LLM."""
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

        chunks = self.pipeline.retrieve(document_id, question)
        if not chunks:
            self.chats.add_message(
                session_id=session_id,
                role="assistant",
                content=INSUFFICIENT_CONTEXT_MESSAGE,
                sources_json=[],
            )
            return INSUFFICIENT_CONTEXT_MESSAGE, []

        answer = self.pipeline.generate(question, chunks)
        sources = [_chunk_to_source(c) for c in chunks]

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

    def ask_stream(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> Iterator[dict[str, Any]]:
        """SSE-style event generator: token chunks, then sources, then done."""
        session_id = self._begin(
            user_id=user_id, document_id=document_id, question=question
        )
        cached = self.cache.get(
            user_id=user_id, document_id=document_id, question=question
        )

        def event_stream() -> Iterator[dict[str, Any]]:
            """Yield token/sources/done events — same shape for cache hit or live LLM."""
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

            chunks = self.pipeline.retrieve(document_id, question)
            if not chunks:
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
            for token in self.pipeline.generate_stream(question, chunks):
                parts.append(token)
                yield {"type": "token", "data": token}

            answer = "".join(parts).strip()
            sources = [_chunk_to_source(c) for c in chunks]
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

    def get_history(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[Message]:
        """Return the persisted messages for this user's session on a document.

        Validates access first (raises `DocumentNotFoundError` if the user may
        not see the document). Returns an empty list if no conversation exists.
        """
        self.documents.get_accessible_document(document_id, user_id)
        session = self.chats.get_session(
            user_id=user_id, document_id=document_id
        )
        if session is None:
            return []
        return self.chats.list_messages(session.id)
