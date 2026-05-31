"""Document service — upload, list, rename, delete, serve original files.

We save the file to disk, create a DB row owned by the user, and kick off
ingestion elsewhere (BackgroundTasks). Parsing/chunking/embeddings live in
the RAG pipeline, not here — keeps uploads fast.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    DocumentFileNotFoundError,
    DocumentNotFoundError,
    InvalidUploadFilenameError,
)
from app.models.document import Document
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.pipeline import RAGPipeline
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.upload_validation import (
    ALLOWED_EXTENSIONS,
    parse_allowed_extension,
    read_upload_bytes,
    sanitize_upload_filename,
    stored_disk_filename,
    validate_upload_content,
)
from app.storage.base import StorageBackend
from app.storage.local_storage import LocalStorage

MEDIA_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# I own upload lifecycle, ingestion trigger, rename, delete, and file download.
class DocumentService:

    # Wire repos, storage backend, and RAG pipeline for this session.
    def __init__(
        self,
        db: Session,
        storage: StorageBackend | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.db = db
        self.documents = DocumentRepository(db)
        self.chunks = ChunkRepository(db)
        self.storage = storage or LocalStorage()
        self.embedder = embedder or get_embedding_service()
        self.pipeline = RAGPipeline(db, embedder=self.embedder)

    # Save a file to storage and create a DB row — returns before ingest finishes.
    # Validates extension, size, content, and filename before writing to disk.
    def upload(
        self, *, owner_id: uuid.UUID, filename: str, fileobj: BinaryIO
    ) -> Document:
        if not filename or not filename.strip():
            raise InvalidUploadFilenameError("Filename must not be empty")

        extension = parse_allowed_extension(filename)
        settings = get_settings()
        data = read_upload_bytes(fileobj, settings.max_upload_bytes)
        validate_upload_content(extension, data)

        safe_filename = sanitize_upload_filename(filename, extension)
        document_id = uuid.uuid4()
        disk_name = stored_disk_filename(document_id, extension)

        storage_path = self.storage.save(
            user_id=owner_id,
            document_id=document_id,
            filename=disk_name,
            fileobj=BytesIO(data),
        )

        try:
            document = self.documents.create(
                document_id=document_id,
                owner_id=owner_id,
                filename=safe_filename,
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

    # Parse, chunk, embed, and save — I update status processing -> ready/failed.
    # Call this from the background worker after upload.
    def ingest(self, document: Document) -> None:
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

    # List every document owned by this user — dashboard view.
    def list_documents(self, owner_id: uuid.UUID) -> list[Document]:
        return self.documents.list_by_owner(owner_id)

    # Fetch one owned document or raise DocumentNotFoundError.
    def get_document(self, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
        document = self.documents.get_owned(document_id, owner_id)
        if document is None:
            raise DocumentNotFoundError()
        return document

    # Set the user-visible display name without renaming the stored file.
    def rename_document(
        self,
        document_id: uuid.UUID,
        owner_id: uuid.UUID,
        display_name: str,
    ) -> Document:
        document = self.get_document(document_id, owner_id)
        return self.documents.update_display_name(document, display_name)

    # Fetch a document the user owns or has future permission to read.
    # Raises DocumentNotFoundError for missing docs and wrong owners alike.
    def get_accessible_document(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> Document:
        document = self.documents.get_owned(document_id, user_id)
        if document is not None:
            return document

        document = self.documents.get_by_id(document_id)
        if document is not None and self.documents.has_permission(
            document_id, user_id
        ):
            return document

        raise DocumentNotFoundError()

    # Return absolute path, media type, and filename for an accessible document.
    # I use the same access checks as chat and never expose storage_path to callers.
    # Raises DocumentFileNotFoundError when the file is missing on disk.
    def get_original_file(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Path, str, str]:
        document = self.get_accessible_document(document_id, user_id)
        path = self.storage.full_path(document.storage_path)
        if not path.is_file():
            raise DocumentFileNotFoundError()

        ext = Path(document.filename).suffix.lower()
        media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
        return path, media_type, document.filename

    # Delete the DB row and remove files from storage for an owned document.
    def delete_document(self, document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        document = self.get_document(document_id, owner_id)
        self.documents.delete(document)
        self.storage.delete_document(user_id=owner_id, document_id=document_id)
