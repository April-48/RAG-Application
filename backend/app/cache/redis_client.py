"""Get a shared Redis client, or None if caching is disabled / package missing.

Connection errors show up on first command, not here — answer_cache handles that.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("app.cache.redis_client")


@lru_cache
def get_redis_client() -> Any | None:
    """Return a shared Redis client, or None if cache is off or setup failed."""
    settings = get_settings()
    if not settings.enable_redis_cache:
        logger.info("Redis cache disabled (ENABLE_REDIS_CACHE is false)")
        return None
    try:
        import redis
    except ImportError:
        logger.warning("redis package not installed; cache disabled")
        return None
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        logger.info("Redis cache enabled (%s)", settings.redis_url)
        return client
    except Exception as exc:
        # Bad URL etc. — treat as "no Redis" and keep going.
        logger.warning("Could not create Redis client (%s); cache disabled", exc)
        return None
