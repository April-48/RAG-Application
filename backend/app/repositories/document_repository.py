"""Database access for the documents table.

Repository layer = raw SQLAlchemy queries, no business rules. DocumentService
calls these methods and adds validation, storage, and ingestion logic on top.

Important pattern: get_owned() always filters by owner_id so users cannot
read each other's files by guessing UUIDs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_permission import DocumentPermission


class DocumentRepository:
    """CRUD and owner-scoped lookups for uploaded file metadata rows."""

    def __init__(self, db: Session) -> None:
        """Store the DB session used for every query in this repository."""
        self.db = db

    def create(
        self,
        *,
        document_id: uuid.UUID,
        owner_id: uuid.UUID,
        filename: str,
        file_type: str | None,
        storage_path: str,
        visibility: str = "private",
        status: str = "uploaded",
    ) -> Document:
        """Insert a new document row right after a successful upload.

        status usually starts as 'uploaded'. Background ingestion moves it through
        processing → ready (or failed). storage_path is relative to the upload root.
        """
        document = Document(
            id=document_id,
            owner_id=owner_id,
            filename=filename,
            file_type=file_type,
            storage_path=storage_path,
            visibility=visibility,
            status=status,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_by_owner(self, owner_id: uuid.UUID) -> list[Document]:
        """List every document owned by this user, newest first — dashboard view."""
        return list(
            self.db.scalars(
                select(Document)
                .where(Document.owner_id == owner_id)
                .order_by(Document.created_at.desc())
            )
        )

    def get_owned(
        self, document_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Document | None:
        """Fetch a document only when it belongs to owner_id.

        Returns None when the id exists but belongs to someone else — callers
        treat that the same as "not found" to avoid leaking ownership info.
        """
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id, Document.owner_id == owner_id
            )
        )

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Lookup by id without an ownership check.

        Only use this when the caller will verify access separately (e.g.
        checking document_permissions for future sharing).
        """
        return self.db.get(Document, document_id)

    def has_permission(self, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return True if user_id has a row in document_permissions.

        Not used in the MVP — every document is private to its owner. The schema
        exists so sharing can be added later without a painful migration.
        """
        return (
            self.db.scalar(
                select(DocumentPermission.id).where(
                    DocumentPermission.document_id == document_id,
                    DocumentPermission.user_id == user_id,
                )
            )
            is not None
        )

    def update_status(self, document: Document, status: str) -> Document:
        """Update lifecycle status and commit.

        Valid values: uploaded, processing, ready, failed. Chat only works when
        status is ready.
        """
        document.status = status
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_display_name(
        self, document: Document, display_name: str
    ) -> Document:
        """Save the user-editable label shown in the UI.

        Does not rename the file on disk — filename stays the original upload name.
        """
        document.display_name = display_name
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        """Remove the document row from Postgres.

        Related chunks and messages cascade via foreign key rules. Caller must
        also delete files from storage (DocumentService does both).
        """
        self.db.delete(document)
        self.db.commit()
