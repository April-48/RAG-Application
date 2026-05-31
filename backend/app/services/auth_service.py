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


# I register users, verify passwords, mint JWTs, and resolve tokens to User rows.
class AuthService:

    # Wire up the user repository for this DB session.
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    # Create an account with a hashed password.
    # Raises EmailAlreadyExistsError if the email is already taken.
    def signup(self, email: str, password: str) -> User:
        if self.users.get_by_email(email) is not None:
            raise EmailAlreadyExistsError(email)
        return self.users.create(
            email=email, password_hash=security.hash_password(password)
        )

    # Check email and password without minting a token.
    # Raises InvalidCredentialsError on a bad pair.
    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        if user is None or not security.verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    # Authenticate and return a JWT access token plus the User row.
    def login(self, email: str, password: str) -> tuple[str, User]:
        user = self.authenticate(email, password)
        token = security.create_access_token(user.id)
        return token, user

    # Decode a JWT subject to user id and load the User — used by get_current_user.
    # Raises InvalidTokenError or UserNotFoundError when the token or user is bad.
    def get_user_from_token(self, token: str) -> User:
        subject = security.decode_access_token(token)
        try:
            user_id = uuid.UUID(subject)
        except (ValueError, TypeError) as exc:
            raise InvalidTokenError() from exc

        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user
