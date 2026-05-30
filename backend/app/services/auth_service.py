"""Signup, login, JWT -> User. Used by auth routes."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    """Register users, verify passwords, mint JWTs, resolve tokens to User rows."""

    def __init__(self, db: Session) -> None:
        """Wire up the user repository for this DB session."""
        self.db = db
        self.users = UserRepository(db)

    def signup(self, email: str, password: str) -> User:
        """Create account with hashed password — raises if email already taken."""
        if self.users.get_by_email(email) is not None:
            raise EmailAlreadyExistsError(email)
        return self.users.create(
            email=email, password_hash=security.hash_password(password)
        )

    def authenticate(self, email: str, password: str) -> User:
        """Check email + password — raises InvalidCredentialsError on mismatch."""
        user = self.users.get_by_email(email)
        if user is None or not security.verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    def login(self, email: str, password: str) -> tuple[str, User]:
        """Authenticate and return (JWT access token, user)."""
        user = self.authenticate(email, password)
        token = security.create_access_token(user.id)
        return token, user

    def get_user_from_token(self, token: str) -> User:
        """Decode JWT subject to user id and load User — used by get_current_user."""
        subject = security.decode_access_token(token)
        try:
            user_id = uuid.UUID(subject)
        except (ValueError, TypeError) as exc:
            raise InvalidTokenError() from exc

        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user
