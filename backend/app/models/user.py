"""User table — email + password hash.

Documents hang off owner_id. That's the main way we enforce "you only see your stuff".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession
    from app.models.document import Document
    from app.models.document_permission import DocumentPermission


class User(Base):
    """Registered account — email login and owner of documents."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[list[Document]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    document_permissions: Mapped[list[DocumentPermission]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
