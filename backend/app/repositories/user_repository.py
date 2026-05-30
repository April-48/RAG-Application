"""User table CRUD — signup lookup, get by id, etc."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Thin SQLAlchemy wrapper around the users table."""

    def __init__(self, db: Session) -> None:
        """Store the DB session this repo uses for all queries."""
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        """Find a user by email — used at signup (duplicate check) and login."""
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: uuid.UUID | str) -> User | None:
        """Load one user by primary key, or None if missing."""
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        return self.db.get(User, user_id)

    def create(self, *, email: str, password_hash: str) -> User:
        """Insert a new user row and return it with generated id/timestamp."""
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
