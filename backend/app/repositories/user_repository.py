"""Database access for the users table.

This is the repository layer — thin SQLAlchemy wrappers with no business rules.
AuthService calls these methods for signup and login. Password hashing happens
in the service layer before create() receives a password_hash string.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Read and write User rows — lookup by email/id, insert new accounts."""

    def __init__(self, db: Session) -> None:
        """Store the DB session used for every query in this repository."""
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        """Find a user by email address.

        Called at signup (check duplicate) and login (load credentials).
        Returns None when no row matches — not an error, just a miss.
        """
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: uuid.UUID | str) -> User | None:
        """Load one user by primary key.

        Accepts UUID or string id (JWT subject is a string). Returns None
        when the user was deleted or the id is unknown.
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        return self.db.get(User, user_id)

    def create(self, *, email: str, password_hash: str) -> User:
        """Insert a new user row and commit.

        Caller must pass an already-hashed password — this repo never sees
        plain text passwords. Returns the committed User with id and created_at.
        """
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
