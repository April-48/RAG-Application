"""Document ORM model — one row per uploaded file.

owner_id is how we make sure users only see their own stuff. filename is the
real uploaded name; display_name is optional UI label the user can rename.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession
    from app.models.chunk import DocumentChunk
    from app.models.document_permission import DocumentPermission
    from app.models.user import User


# ORM row for one uploaded file — owner, status, and on-disk path.
# I track lifecycle status from uploaded through processing to ready/failed.
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # 'private' | 'shared' — sharing not implemented yet
    visibility: Mapped[str] = mapped_column(
        String(32), default="private", server_default="private", nullable=False
    )
    # Lifecycle: uploaded -> processing -> ready (or failed)
    status: Mapped[str] = mapped_column(
        String(32), default="uploaded", server_default="uploaded", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        back_populates="document"
    )
    permissions: Mapped[list[DocumentPermission]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
