"""Enforce per-user chat rate limits before LLM endpoints run."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.cache.rate_limiter import ChatRateLimiter
from app.models.user import User

from .get_current_user import get_current_user


def get_current_user_with_chat_rate_limit(
    current_user: User = Depends(get_current_user),
) -> User:
    """Authenticate the user and reject chat asks over the per-minute Redis cap."""
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
