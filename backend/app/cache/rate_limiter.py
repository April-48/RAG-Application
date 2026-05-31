"""Per-user chat rate limiting via Redis — optional, fail-open.

Key: rate:user:{user_id}:chat:{yyyyMMddHHmm}
Uses INCR + EXPIRE (60s). Only enforced when ENABLE_RATE_LIMIT=true.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.cache.redis_client import get_redis_rate_limit_client
from app.core.config import get_settings

logger = logging.getLogger("app.cache.rate_limiter")

RATE_KEY_PREFIX = "rate:user"


# Outcome of a chat rate-limit check — allowed flag plus optional retry_after.
@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int | None = None


# Redis INCR counter per user per calendar minute for chat requests.
# I fail open when Redis is down so chat still works.
class ChatRateLimiter:

    # Use an injected Redis client in tests; otherwise get_redis_rate_limit_client().
    def __init__(self, client: Any | None = None) -> None:
        self._client = (
            client if client is not None else get_redis_rate_limit_client()
        )

    # Return whether this chat request is under the per-minute cap.
    # Output: RateLimitResult with allowed=True, or retry_after when blocked.
    def check(self, user_id: uuid.UUID) -> RateLimitResult:
        settings = get_settings()
        if not settings.enable_rate_limit:
            return RateLimitResult(allowed=True)

        if self._client is None:
            logger.debug("Rate limit skipped (Redis unavailable or disabled)")
            return RateLimitResult(allowed=True)

        try:
            now = datetime.now(timezone.utc)
            key = (
                f"{RATE_KEY_PREFIX}:{user_id}:chat:"
                f"{now.strftime('%Y%m%d%H%M')}"
            )
            count = int(self._client.incr(key))
            if count == 1:
                self._client.expire(key, 60)

            if count > settings.chat_rate_limit_per_minute:
                retry_after = 60 - now.second or 60
                logger.info(
                    "Chat rate limit exceeded user=%s count=%s limit=%s",
                    user_id,
                    count,
                    settings.chat_rate_limit_per_minute,
                )
                return RateLimitResult(allowed=False, retry_after=retry_after)

            return RateLimitResult(allowed=True)
        except Exception as exc:
            logger.warning(
                "Rate limit check failed (%s); allowing request", exc
            )
            return RateLimitResult(allowed=True)
