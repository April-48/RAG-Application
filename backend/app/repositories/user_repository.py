"""User table CRUD — signup lookup, get by id, etc."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


# Thin SQLAlchemy wrapper around the users table — no business rules here.
class UserRepository:

    # Store the DB session this repo uses for every query.
    def __init__(self, db: Session) -> None:
        self.db = db

    # Find a user by email — I call this at signup and login.
    # Output: User row or None if no match.
    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    # Load one user by primary key.
    # Accepts UUID or string id. Output: User row or None if missing.
    def get_by_id(self, user_id: uuid.UUID | str) -> User | None:
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        return self.db.get(User, user_id)

    # Insert a new user row with a precomputed password hash.
    # Output: committed User with generated id and created_at.
    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
