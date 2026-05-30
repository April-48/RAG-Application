"""Embed the question, search pgvector — always scoped to one document_id."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.rag.embedding_service import Embedder, get_embedding_service
from app.repositories.chunk_repository import ChunkRepository


class RetrievalService:
    """Embed a question and run pgvector search scoped to one document."""

    def __init__(self, db: Session, embedder: Embedder | None = None) -> None:
        """Wire chunk repo and embedder for similarity search."""
        self.chunks = ChunkRepository(db)
        self.embedder = embedder or get_embedding_service()

    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> list[DocumentChunk]:
        """Return top-k chunks most similar to the question for this document."""
        top_k = top_k or get_settings().retrieval_top_k
        query_embedding = self.embedder.embed_query(question)
        return self.chunks.search_by_document(document_id, query_embedding, top_k)
