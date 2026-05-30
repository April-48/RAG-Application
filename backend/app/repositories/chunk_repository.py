"""Chunk + embedding storage and pgvector similarity search.

search_by_document always scopes to one document_id — never cross-doc retrieval.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.rag.text_splitter import Chunk


class ChunkRepository:
    """Persist and search document_chunks rows (text + pgvector embedding)."""

    def __init__(self, db: Session) -> None:
        """Store the DB session this repo uses for all queries."""
        self.db = db

    def create_many(self, document_id: uuid.UUID, chunks: list[Chunk]) -> int:
        """Bulk-insert embedded chunks after ingestion — returns how many rows saved."""
        rows = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                chunk_text=chunk.chunk_text,
                embedding=chunk.embedding,
            )
            for chunk in chunks
        ]
        self.db.add_all(rows)
        self.db.commit()
        return len(rows)

    def search_by_document(
        self,
        document_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[DocumentChunk]:
        """Top-k nearest chunks for this document only (cosine distance in pgvector)."""
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.embedding.is_not(None),
                )
                .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
                .limit(top_k)
            )
        )

    def list_by_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        """All chunks for a doc in chunk_index order — mostly for debugging/re-ingest."""
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    def count_by_document(self, document_id: uuid.UUID) -> int:
        """How many chunks exist for this document."""
        return len(self.list_by_document(document_id))

    def delete_by_document(self, document_id: uuid.UUID) -> None:
        """Wipe all chunks for a doc — used before re-ingest or on delete."""
        self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.db.commit()
