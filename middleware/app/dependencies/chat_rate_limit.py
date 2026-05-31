"""FastAPI dependency that rate-limits chat ask routes via Redis."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.cache.rate_limiter import ChatRateLimiter
from app.models.user import User

from .get_current_user import get_current_user


# FastAPI dependency for POST /chat/{document_id}/ask and /ask/stream only.
# Step 1: get_current_user reads the Bearer JWT and loads the User from Postgres.
# Step 2: ChatRateLimiter increments a Redis counter for this user and calendar minute.
# Return the User when the count is at or below the cap (default 10 asks per minute).
# Raise HTTP 429 with a Retry-After header when the user is over the cap.
# If ENABLE_RATE_LIMIT is off or Redis is down, I skip the check and allow the request.
def get_current_user_with_chat_rate_limit(
    current_user: User = Depends(get_current_user),
) -> User:
    result = ChatRateLimiter().check(user_id=current_user.id)
    if result.allowed:
        return current_user

    headers: dict[str, str] = {}
    if result.retry_after is not None:
        headers["Retry-After"] = str(result.retry_after)

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please wait a moment and try again.",
        headers=headers or None,
    )
