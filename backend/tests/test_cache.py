"""Redis answer cache key and fail-open behavior."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

from app.cache.answer_cache import AnswerCache, build_cache_key, build_document_cache_pattern


def test_cache_key_includes_user_document_and_question_hash() -> None:
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key = build_cache_key(user_id, document_id, "What is this?")

    assert key.startswith("rag:answer:")
    assert str(user_id) in key
    assert str(document_id) in key
    parts = key.split(":")
    assert len(parts) == 5
    assert len(parts[-1]) == 64  # sha256 hex


def test_normalized_questions_share_cache_key() -> None:
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    key_a = build_cache_key(user_id, document_id, "What is this?")
    key_b = build_cache_key(user_id, document_id, " what is this? ")
    assert key_a == key_b


def test_different_user_or_document_changes_key() -> None:
    document_id = uuid.uuid4()
    base_key = build_cache_key(uuid.uuid4(), document_id, "What is this?")
    other_user_key = build_cache_key(uuid.uuid4(), document_id, "What is this?")
    other_doc_key = build_cache_key(
        uuid.UUID(base_key.split(":")[2]), uuid.uuid4(), "What is this?"
    )
    assert base_key != other_user_key
    assert base_key != other_doc_key


def test_redis_get_failure_fails_open() -> None:
    client = MagicMock()
    client.get.side_effect = RuntimeError("connection refused")
    cache = AnswerCache(client=client)

    result = cache.get(
        user_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        question="hello",
    )
    assert result is None


def test_redis_set_failure_does_not_raise() -> None:
    client = MagicMock()
    client.set.side_effect = RuntimeError("connection refused")
    cache = AnswerCache(client=client)

    cache.set(
        user_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        question="hello",
        answer="world",
        sources=[],
    )


def test_cache_round_trip_with_fake_redis() -> None:
    store: dict[str, str] = {}

    class FakeRedis:
        def get(self, key: str) -> str | None:
            return store.get(key)

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            store[key] = value

    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    cache = AnswerCache(client=FakeRedis())
    cache.set(
        user_id=user_id,
        document_id=document_id,
        question="Summary?",
        answer="A short summary.",
        sources=[{"chunk_index": 0, "page_number": 1, "chunk_text": "ctx"}],
    )
    payload = cache.get(
        user_id=user_id, document_id=document_id, question=" summary? "
    )
    assert payload is not None
    assert payload["answer"] == "A short summary."
    assert payload["sources"][0]["chunk_text"] == "ctx"


def test_clear_for_document_removes_matching_keys() -> None:
    store: dict[str, str] = {}

    class FakeRedis:
        def get(self, key: str) -> str | None:
            return store.get(key)

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            store[key] = value

        def delete(self, key: str) -> None:
            store.pop(key, None)

        def scan_iter(self, *, match: str) -> list[str]:
            prefix = match[:-1] if match.endswith("*") else match
            return [key for key in store if key.startswith(prefix)]

    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    other_document_id = uuid.uuid4()
    cache = AnswerCache(client=FakeRedis())
    cache.set(
        user_id=user_id,
        document_id=document_id,
        question="Q1",
        answer="A1",
        sources=[],
    )
    cache.set(
        user_id=user_id,
        document_id=document_id,
        question="Q2",
        answer="A2",
        sources=[],
    )
    cache.set(
        user_id=user_id,
        document_id=other_document_id,
        question="Q3",
        answer="A3",
        sources=[],
    )

    cleared = cache.clear_for_document(user_id=user_id, document_id=document_id)

    assert cleared == 2
    assert cache.get(user_id=user_id, document_id=document_id, question="Q1") is None
    assert cache.get(user_id=user_id, document_id=document_id, question="Q2") is None
    assert (
        cache.get(user_id=user_id, document_id=other_document_id, question="Q3")
        is not None
    )


def test_document_cache_pattern() -> None:
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    pattern = build_document_cache_pattern(user_id, document_id)
    key = build_cache_key(user_id, document_id, "hello")
    assert pattern == f"rag:answer:{user_id}:{document_id}:*"
    assert key.startswith(pattern[:-1])
