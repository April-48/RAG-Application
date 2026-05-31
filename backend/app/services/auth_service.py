"""User signup, login, and JWT validation.

This is the auth business layer — routes call us, we talk to UserRepository
and security helpers. Flow for a typical request:
  1. User signs up → hash password → save User row
  2. User logs in → verify password → mint JWT with user id inside
  3. Later requests send Bearer token → decode JWT → load User row

We never return password hashes to the API layer.
"""

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
    """Handle account creation, login, and resolving JWT tokens to User rows."""

    def __init__(self, db: Session) -> None:
        """Store the DB session and create a UserRepository for this request."""
        self.db = db
        self.users = UserRepository(db)

    def signup(self, email: str, password: str) -> User:
        """Create a new account with a bcrypt-hashed password.

        Raises EmailAlreadyExistsError if that email is already registered.
        Returns the new User row (without ever exposing the raw password).
        """
        if self.users.get_by_email(email) is not None:
            raise EmailAlreadyExistsError(email)
        return self.users.create(
            email=email, password_hash=security.hash_password(password)
        )

    def authenticate(self, email: str, password: str) -> User:
        """Check email + password without minting a token.

        Used internally by login(). Raises InvalidCredentialsError when the
        email is unknown or the password does not match the stored hash.
        """
        user = self.users.get_by_email(email)
        if user is None or not security.verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    def login(self, email: str, password: str) -> tuple[str, User]:
        """Verify credentials and return (JWT access token, User row).

        The token subject is the user's UUID string. Middleware passes it on
        every authenticated request as Authorization: Bearer <token>.
        """
        user = self.authenticate(email, password)
        token = security.create_access_token(user.id)
        return token, user

    def get_user_from_token(self, token: str) -> User:
        """Decode a JWT and load the matching User row.

        Called by middleware get_current_user on every protected route.
        Raises InvalidTokenError when the token is bad or expired.
        Raises UserNotFoundError when the token is valid but the user was deleted.
        """
        subject = security.decode_access_token(token)
        try:
            user_id = uuid.UUID(subject)
        except (ValueError, TypeError) as exc:
            raise InvalidTokenError() from exc

        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user
