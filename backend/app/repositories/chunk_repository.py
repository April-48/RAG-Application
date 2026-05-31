"""Chunk + embedding storage and pgvector similarity search.

search_by_document always scopes to one document_id — never cross-doc retrieval.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.rag.text_splitter import Chunk


# Persist and search document_chunks rows (text + pgvector embedding).
class ChunkRepository:

    # Store the DB session this repo uses for every query.
    def __init__(self, db: Session) -> None:
        self.db = db

    # Bulk-insert embedded chunks after ingestion.
    # Output: count of rows saved.
    def create_many(self, document_id: uuid.UUID, chunks: list[Chunk]) -> int:
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

    # Return top-k nearest chunks for this document only (cosine distance).
    # Input: document_id, query embedding vector, and optional top_k.
    def search_by_document(
        self,
        document_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[DocumentChunk]:
        return [chunk for chunk, _distance in self.search_by_document_with_distance(
            document_id, query_embedding, top_k
        )]

    # Return top-k chunks plus pgvector cosine distance (lower = more similar).
    # Results are ordered ascending by distance — best match first.
    def search_by_document_with_distance(
        self,
        document_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label(
            "distance"
        )
        rows = self.db.execute(
            select(DocumentChunk, distance)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        ).all()
        return [(row[0], float(row[1])) for row in rows]

    # Return the earliest chunk for a document (chunk_index ASC, limit 1).
    def get_first_chunk(self, document_id: uuid.UUID) -> DocumentChunk | None:
        return self.db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(1)
        )

    # Return the latest chunk for a document (chunk_index DESC, limit 1).
    def get_last_chunk(self, document_id: uuid.UUID) -> DocumentChunk | None:
        return self.db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.desc())
            .limit(1)
        )

    # Return all chunks on one page in document order.
    def get_chunks_by_page(
        self, document_id: uuid.UUID, page_number: int
    ) -> list[DocumentChunk]:
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.page_number == page_number,
                )
                .order_by(DocumentChunk.chunk_index)
            )
        )

    # True when at least one chunk for this document stores a page_number.
    def has_page_metadata(self, document_id: uuid.UUID) -> bool:
        count = self.db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.page_number.is_not(None),
            )
        )
        return bool(count)

    # List all chunks for a doc in chunk_index order — debug and re-ingest.
    def list_by_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    # Count how many chunks exist for this document.
    def count_by_document(self, document_id: uuid.UUID) -> int:
        return len(self.list_by_document(document_id))

    # Wipe all chunks for a doc — I call this before re-ingest or on failure.
    def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.db.commit()
