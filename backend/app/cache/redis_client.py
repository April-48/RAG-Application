"""Get shared Redis clients for cache and rate limiting.

Both features are optional and fail-open — if Redis is down or disabled in .env,
the app keeps working without caching or rate limits. I use @lru_cache so every
AnswerCache and ChatRateLimiter instance shares one connection pool per purpose.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("app.cache.redis_client")


# Build a Redis client from a URL, or return None on import/setup failure.
# I log which purpose (cache vs rate limit) failed so ops can spot misconfig.
def _create_redis_client(redis_url: str, purpose: str) -> Any | None:
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


# Return a shared Redis client for the answer cache, or None if cache is off.
# I cache the client so every AnswerCache instance shares one connection pool.
@lru_cache
def get_redis_client() -> Any | None:
    settings = get_settings()
    if not settings.enable_redis_cache:
        logger.info("Redis cache disabled (ENABLE_REDIS_CACHE is false)")
        return None
    return _create_redis_client(settings.redis_url, "cache")


# Return a shared Redis client for rate limiting, or None if disabled.
# I use a separate cached client so cache and limiter toggles stay independent.
@lru_cache
def get_redis_rate_limit_client() -> Any | None:
    settings = get_settings()
    if not settings.enable_rate_limit:
        logger.info("Rate limiting disabled (ENABLE_RATE_LIMIT is false)")
        return None
    return _create_redis_client(settings.redis_url, "rate limit")
