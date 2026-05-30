"""Document service — upload, list, rename, delete, serve original files.

We save the file to disk, create a DB row owned by the user, and kick off
ingestion elsewhere (BackgroundTasks). Parsing/chunking/embeddings live in
the RAG pipeline, not here — keeps uploads fast.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DocumentFileNotFoundError,
    DocumentNotFoundError,
    UnsupportedFileTypeError,
)
from app.models.document import Document
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.pipeline import RAGPipeline
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.storage.base import StorageBackend
from app.storage.local_storage import LocalStorage

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}

MEDIA_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class DocumentService:
    """Owns upload lifecycle, ingestion trigger, rename, delete, and file download."""

    def __init__(
        self,
        db: Session,
        storage: StorageBackend | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        """Wire repos, storage backend, and RAG pipeline for this session."""
        self.db = db
        self.documents = DocumentRepository(db)
        self.chunks = ChunkRepository(db)
        self.storage = storage or LocalStorage()
        self.embedder = embedder or get_embedding_service()
        self.pipeline = RAGPipeline(db, embedder=self.embedder)

    def upload(
        self, *, owner_id: uuid.UUID, filename: str, fileobj: BinaryIO
    ) -> Document:
        """Save file to storage, create DB row — returns immediately (ingest is async)."""
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(extension)

        document_id = uuid.uuid4()
        storage_path = self.storage.save(
            user_id=owner_id,
            document_id=document_id,
            filename=filename,
            fileobj=fileobj,
        )

        try:
            document = self.documents.create(
                document_id=document_id,
                owner_id=owner_id,
                filename=Path(filename).name,
                file_type=extension.lstrip("."),
                storage_path=storage_path,
                visibility="private",
                status="uploaded",
            )
        except Exception:
            # DB insert failed — delete the file we just wrote so we don't orphan it.
            self.storage.delete_document(user_id=owner_id, document_id=document_id)
            raise

        # Ingestion runs in BackgroundTasks (ingestion_worker), not here —
        # so upload returns fast with status "uploaded".
        return document

    def ingest(self, document: Document) -> None:
        """Parse file, chunk, embed, save. Updates status processing -> ready/failed."""
        self.documents.update_status(document, "processing")
        try:
            created = self.pipeline.ingest(
                document_id=document.id,
                file_path=self.storage.full_path(document.storage_path),
                file_type=document.file_type,
            )
        except Exception:
            # Don't leave half-finished chunks lying around.
            self.chunks.delete_by_document(document.id)
            self.documents.update_status(document, "failed")
            return

        if created == 0:
            self.documents.update_status(document, "failed")
            return

        self.documents.update_status(document, "ready")

    def list_documents(self, owner_id: uuid.UUID) -> list[Document]:
        """Dashboard list — all docs for this user."""
        return self.documents.list_by_owner(owner_id)

    def get_document(self, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
        """Fetch one owned document or raise DocumentNotFoundError."""
        document = self.documents.get_owned(document_id, owner_id)
        if document is None:
            raise DocumentNotFoundError()
        return document

    def rename_document(
        self,
        document_id: uuid.UUID,
        owner_id: uuid.UUID,
        display_name: str,
    ) -> Document:
        """Set the user-visible display name without changing the stored file."""
        document = self.get_document(document_id, owner_id)
        return self.documents.update_display_name(document, display_name)

    def get_accessible_document(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> Document:
        """Same 404 whether doc missing or belongs to someone else — no leaking."""
        document = self.documents.get_owned(document_id, user_id)
        if document is not None:
            return document

        document = self.documents.get_by_id(document_id)
        if document is not None and self.documents.has_permission(
            document_id, user_id
        ):
            return document

        raise DocumentNotFoundError()

    def get_original_file(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Path, str, str]:
        """Return absolute path, media type, and filename for an accessible document.

        Uses the same ownership/permission checks as chat. Does not expose
        `storage_path` to callers.
        """
        document = self.get_accessible_document(document_id, user_id)
        path = self.storage.full_path(document.storage_path)
        if not path.is_file():
            raise DocumentFileNotFoundError()

        ext = Path(document.filename).suffix.lower()
        media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
        return path, media_type, document.filename

    def delete_document(self, document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        """Delete DB row and remove files from storage for an owned document."""
        document = self.get_document(document_id, owner_id)
        self.documents.delete(document)
        self.storage.delete_document(user_id=owner_id, document_id=document_id)
