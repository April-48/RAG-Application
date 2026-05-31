"""Persist document chunks and run pgvector similarity search.

Each row in document_chunks holds one text slice plus its embedding vector.
search_by_document* always filters by document_id — retrieval never mixes chunks
from different uploads, even for the same user.

pgvector uses cosine distance: 0 means identical direction, higher means less
similar. RetrievalService converts that to similarity as 1.0 - distance.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.rag.text_splitter import Chunk


class ChunkRepository:
    """Save embedded chunks and query them by position, page, or vector similarity."""

    def __init__(self, db: Session) -> None:
        """Store the DB session used for every query in this repository."""
        self.db = db

    def create_many(self, document_id: uuid.UUID, chunks: list[Chunk]) -> int:
        """Bulk-insert embedded chunks after ingestion finishes.

        Input is the in-memory Chunk list from text_splitter (with embeddings
        already filled in). Returns the number of rows saved.
        """
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
        top_k: int = 8,
    ) -> list[DocumentChunk]:
        """Return top-k nearest chunks for this document (chunks only, no scores).

        Convenience wrapper around search_by_document_with_distance().
        top_k defaults to 8 as a fallback — callers should pass settings.retrieval_top_k.
        """
        return [chunk for chunk, _distance in self.search_by_document_with_distance(
            document_id, query_embedding, top_k
        )]

    def search_by_document_with_distance(
        self,
        document_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 8,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return top-k chunks plus pgvector cosine distance for each hit.

        Results are ordered best-first (lowest distance). Chunks without an
        embedding column value are excluded from search.
        """
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

    def get_first_chunk(self, document_id: uuid.UUID) -> DocumentChunk | None:
        """Return the chunk with the lowest chunk_index — start of the document."""
        return self.db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(1)
        )

    def get_last_chunk(self, document_id: uuid.UUID) -> DocumentChunk | None:
        """Return the chunk with the highest chunk_index — end of the document."""
        return self.db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.desc())
            .limit(1)
        )

    def get_chunks_by_page(
        self, document_id: uuid.UUID, page_number: int
    ) -> list[DocumentChunk]:
        """Return all chunks tagged with a given PDF page number, in chunk order."""
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

    def has_page_metadata(self, document_id: uuid.UUID) -> bool:
        """Return True when at least one chunk stores a non-null page_number.

        TXT and DOCX uploads never get page numbers, so page lookup questions
        fall back to semantic search for those file types.
        """
        count = self.db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.page_number.is_not(None),
            )
        )
        return bool(count)

    def list_by_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        """Return every chunk for a document in chunk_index order.

        Used for section lookup (scan all headings) and debug/re-ingest tooling.
        """
        return list(
            self.db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )

    def count_by_document(self, document_id: uuid.UUID) -> int:
        """Return how many chunks exist for this document."""
        return len(self.list_by_document(document_id))

    def delete_by_document(self, document_id: uuid.UUID) -> None:
        """Delete all chunks for a document.

        Called before re-ingest and when ingestion fails mid-way so we do not
        leave half-finished chunk rows in the database.
        """
        self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.db.commit()
