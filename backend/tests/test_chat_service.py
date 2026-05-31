"""ChatService tests with mocked retrieval/LLM — no real API calls."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.cache.answer_cache import AnswerCache
from app.core.exceptions import DocumentNotReadyError, LLMError
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.rag.query_router import QueryMode, RoutedQuery
from app.rag.retrieval_service import RetrievalResult
from app.services.chat_service import ChatService, ClearHistoryResult


def _ready_document(owner_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        filename="demo.txt",
        file_type="txt",
        storage_path="u/d/demo.txt",
        visibility="private",
        status="ready",
    )


def _processing_document(owner_id: uuid.UUID) -> Document:
    doc = _ready_document(owner_id)
    doc.status = "processing"
    return doc


def _sample_chunk(document_id: uuid.UUID) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_index=0,
        page_number=1,
        chunk_text="The warranty lasts two years.",
        embedding=None,
    )


class MockLLM:
    def generate(self, messages: list[dict[str, str]]) -> str:
        return "The warranty lasts two years."

    def generate_stream(self, messages: list[dict[str, str]]):
        yield "The warranty lasts two years."


def test_ask_on_non_ready_document_raises(db_session) -> None:
    user_id = uuid.uuid4()
    document = _processing_document(user_id)

    documents = MagicMock()
    documents.get_accessible_document.return_value = document

    chats = MagicMock()
    chats.get_or_create_session.return_value = MagicMock(id=uuid.uuid4())

    service = ChatService(
        db_session,
        documents=documents,
        chats=chats,
        cache=AnswerCache(client=None),
        pipeline=MagicMock(),
    )

    with pytest.raises(DocumentNotReadyError):
        service.ask(
            user_id=user_id,
            document_id=document.id,
            question="How long is the warranty?",
        )


def test_ask_returns_mocked_answer_and_sources(db_session) -> None:
    user_id = uuid.uuid4()
    document = _ready_document(user_id)
    chunk = _sample_chunk(document.id)

    documents = MagicMock()
    documents.get_accessible_document.return_value = document

    session_id = uuid.uuid4()
    chats = MagicMock()
    chats.get_or_create_session.return_value = MagicMock(id=session_id)

    pipeline = MagicMock()
    pipeline.retrieve.return_value = RetrievalResult(
        chunks=[chunk],
        routed=RoutedQuery(mode=QueryMode.SEMANTIC),
    )
    pipeline.generate.return_value = "The warranty lasts two years."

    cache = AnswerCache(client=None)
    service = ChatService(
        db_session,
        documents=documents,
        chats=chats,
        cache=cache,
        pipeline=pipeline,
        llm=MockLLM(),
    )

    answer, sources = service.ask(
        user_id=user_id,
        document_id=document.id,
        question="How long is the warranty?",
    )

    assert answer == "The warranty lasts two years."
    assert len(sources) == 1
    assert sources[0]["chunk_index"] == 0
    assert sources[0]["page_number"] == 1
    assert "warranty" in sources[0]["chunk_text"]
    pipeline.retrieve.assert_called_once()
    pipeline.generate.assert_called_once()
    assert chats.add_message.call_count >= 2


def test_llm_error_propagates_from_pipeline(db_session) -> None:
    user_id = uuid.uuid4()
    document = _ready_document(user_id)
    chunk = _sample_chunk(document.id)

    documents = MagicMock()
    documents.get_accessible_document.return_value = document

    chats = MagicMock()
    chats.get_or_create_session.return_value = MagicMock(id=uuid.uuid4())

    pipeline = MagicMock()
    pipeline.retrieve.return_value = RetrievalResult(
        chunks=[chunk],
        routed=RoutedQuery(mode=QueryMode.SEMANTIC),
    )
    pipeline.generate.side_effect = LLMError("LLM request failed")

    service = ChatService(
        db_session,
        documents=documents,
        chats=chats,
        cache=AnswerCache(client=None),
        pipeline=pipeline,
    )

    with pytest.raises(LLMError):
        service.ask(
            user_id=user_id,
            document_id=document.id,
            question="Trigger failure",
        )


def test_clear_history_deletes_messages_and_returns_count(db_session) -> None:
    user_id = uuid.uuid4()
    document = _ready_document(user_id)
    session_id = uuid.uuid4()

    documents = MagicMock()
    documents.get_accessible_document.return_value = document

    chats = MagicMock()
    chats.get_session.return_value = MagicMock(id=session_id)
    chats.clear_messages.return_value = 4

    cache = MagicMock()
    cache.clear_for_document.return_value = 2

    service = ChatService(
        db_session,
        documents=documents,
        chats=chats,
        cache=cache,
        pipeline=MagicMock(),
    )

    result = service.clear_history(user_id=user_id, document_id=document.id)

    assert result == ClearHistoryResult(deleted=4, cache_cleared=2)
    documents.get_accessible_document.assert_called_once_with(document.id, user_id)
    chats.get_session.assert_called_once_with(
        user_id=user_id, document_id=document.id
    )
    chats.clear_messages.assert_called_once_with(session_id)
    cache.clear_for_document.assert_called_once_with(
        user_id=user_id, document_id=document.id
    )


def test_clear_history_returns_zero_when_no_session(db_session) -> None:
    user_id = uuid.uuid4()
    document = _ready_document(user_id)

    documents = MagicMock()
    documents.get_accessible_document.return_value = document

    chats = MagicMock()
    chats.get_session.return_value = None

    cache = MagicMock()
    cache.clear_for_document.return_value = 0

    service = ChatService(
        db_session,
        documents=documents,
        chats=chats,
        cache=cache,
        pipeline=MagicMock(),
    )

    result = service.clear_history(user_id=user_id, document_id=document.id)

    assert result == ClearHistoryResult(deleted=0, cache_cleared=0)
    chats.clear_messages.assert_not_called()
    cache.clear_for_document.assert_called_once_with(
        user_id=user_id, document_id=document.id
    )
