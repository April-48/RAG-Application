"""Password hashing (bcrypt) and JWT create/decode.

Plain functions — auth_service and middleware both use these. No FastAPI here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# I hash a plaintext password with bcrypt before storing it on User.
# Input: raw password string. Output: bcrypt hash string.
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# I check a login password against the stored bcrypt hash.
# Input: plaintext password and stored hash. Output: True if they match.
def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# I mint a signed JWT whose `sub` claim holds the user id.
# Input: subject (user id) and optional expiry override.
# Output: encoded JWT string. Default TTL comes from settings.
def create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# I decode and verify a JWT, then return its subject (user id).
# Raises InvalidTokenError if the token is malformed, expired, or lacks `sub`.
def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise InvalidTokenError() from exc

    subject = payload.get("sub")
    if subject is None:
        raise InvalidTokenError()
    return subject
