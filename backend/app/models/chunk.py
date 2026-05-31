"""document_chunks table — text snippets + pgvector embedding per document.

Retrieval always filters by document_id so we never leak chunks across users/docs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document

EMBEDDING_DIM = get_settings().embedding_dim


# ORM row for one text slice plus its pgvector embedding.
# I always scope retrieval by document_id so chunks never cross documents.
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: a chunk exists before its embedding is computed.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
