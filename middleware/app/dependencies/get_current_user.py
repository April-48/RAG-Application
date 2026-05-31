"""FastAPI dependency that turns a Bearer JWT into a User row."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.exceptions import InvalidTokenError, UserNotFoundError
from app.models.user import User
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# FastAPI dependency used on any route that needs a logged-in user.
# Read Authorization: Bearer <jwt> from the request header.
# Call AuthService.get_user_from_token to decode the JWT and load the User row.
# Return the User on success.
# Raise HTTP 401 (same message every time) if the token is missing, invalid, or expired.
def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise _credentials_exception
    try:
        return AuthService(db).get_user_from_token(token)
    except (InvalidTokenError, UserNotFoundError) as exc:
        raise _credentials_exception from exc
