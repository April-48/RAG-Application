"""Get shared Redis clients for cache and rate limiting (fail-open when disabled)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("app.cache.redis_client")


def _create_redis_client(redis_url: str, purpose: str) -> Any | None:
    """Build a Redis client or return None on import/setup failure."""
    try:
        import redis
    except ImportError:
        logger.warning("redis package not installed; %s disabled", purpose)
        return None
    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        logger.info("Redis %s enabled (%s)", purpose, redis_url)
        return client
    except Exception as exc:
        logger.warning(
            "Could not create Redis client for %s (%s); disabled", purpose, exc
        )
        return None


@lru_cache
def get_redis_client() -> Any | None:
    """Return a shared Redis client for answer cache, or None if cache is off."""
    settings = get_settings()
    if not settings.enable_redis_cache:
        logger.info("Redis cache disabled (ENABLE_REDIS_CACHE is false)")
        return None
    return _create_redis_client(settings.redis_url, "cache")


@lru_cache
def get_redis_rate_limit_client() -> Any | None:
    """Return a shared Redis client for rate limiting, or None if disabled."""
    settings = get_settings()
    if not settings.enable_rate_limit:
        logger.info("Rate limiting disabled (ENABLE_RATE_LIMIT is false)")
        return None
    return _create_redis_client(settings.redis_url, "rate limit")
