"""Redis cache for repeat questions — optional, never breaks chat if Redis is down.

Key: rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}
We lowercase/trim only for the key ("Hello" and "hello" share an entry).
Value: JSON {answer, sources}. Miss or error = just run RAG normally.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from app.cache.redis_client import get_redis_client
from app.core.config import get_settings

logger = logging.getLogger("app.cache.answer_cache")

CACHE_KEY_PREFIX = "rag:answer"


def _question_hash(question: str) -> str:
    """SHA-256 of normalized question text — part of the Redis cache key."""
    # Lowercase/trim only for the cache key — real question text stays as typed.
    normalized_question = question.strip().lower()
    return hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()


def build_cache_key(
    user_id: uuid.UUID, document_id: uuid.UUID, question: str
) -> str:
    """Full Redis key: rag:answer:{user}:{doc}:{question_hash}."""
    return (
        f"{CACHE_KEY_PREFIX}:{user_id}:{document_id}:{_question_hash(question)}"
    )


class AnswerCache:
    """Thin wrapper around Redis for (user, doc, question) -> answer + sources."""

    def __init__(self, client: Any | None = None) -> None:
        """Use injected Redis client in tests; otherwise shared get_redis_client()."""
        # Tests can inject a fake client; prod uses get_redis_client() or None.
        self._client = client if client is not None else get_redis_client()
        self._ttl = get_settings().cache_ttl_seconds

    @property
    def enabled(self) -> bool:
        """True when we have a Redis client (cache feature is on)."""
        return self._client is not None

    def get(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID, question: str
    ) -> dict[str, Any] | None:
        """Look up cached answer + sources, or None on miss / any Redis problem."""
        if self._client is None:
            logger.debug("Redis cache disabled; skipping lookup")
            return None
        key = build_cache_key(user_id, document_id, question)
        try:
            raw = self._client.get(key)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s); falling back to normal RAG flow", exc
            )
            return None  # Redis down — pretend cache miss, keep chatting.
        if not raw:
            logger.info("Redis cache miss for %s", key)
            return None
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Discarding malformed cache entry for %s", key)
            return None
        if not isinstance(payload, dict) or "answer" not in payload:
            logger.warning("Discarding malformed cache entry for %s", key)
            return None
        payload.setdefault("sources", [])
        logger.info("Redis cache hit for %s", key)
        return payload

    def set(
        self,
        *,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        question: str,
        answer: str,
        sources: list[dict[str, Any]],
    ) -> None:
        """Cache an answer + its sources. No-op on any failure."""
        if self._client is None:
            return
        key = build_cache_key(user_id, document_id, question)
        try:
            value = json.dumps({"answer": answer, "sources": sources})
            self._client.set(key, value, ex=self._ttl)
            logger.info("Redis cache set for %s (ttl=%ss)", key, self._ttl)
        except Exception as exc:
            logger.warning(
                "Redis cache set failed (%s); continuing without cache", exc
            )
            return  # Don't fail the request just because cache write failed.
