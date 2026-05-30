"""Future sharing table — not used in MVP yet.

Lets you grant another user read access to a doc you own. Schema exists so we
don't need a painful migration later.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class DocumentPermission(Base):
    """Future row granting another user access to someone's document (schema only)."""

    __tablename__ = "document_permissions"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_document_user_permission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'read' | 'write' (future use)
    permission: Mapped[str] = mapped_column(
        String(32), default="read", server_default="read", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="permissions")
    user: Mapped[User] = relationship(back_populates="document_permissions")
