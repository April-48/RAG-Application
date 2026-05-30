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


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT whose `sub` claim is the given subject (user id)."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Decode/verify a JWT and return its subject (user id).

    Raises:
        InvalidTokenError: if the token is malformed, expired, or missing `sub`.
    """
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
