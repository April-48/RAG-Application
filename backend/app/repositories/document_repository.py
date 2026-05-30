"""Document DB queries — always filtered by owner_id when it matters.

Repository layer = raw SQLAlchemy, no business rules. Services call us.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_permission import DocumentPermission


class DocumentRepository:
    """CRUD and owner-scoped lookups for the documents table."""

    def __init__(self, db: Session) -> None:
        """Store the DB session this repo uses for all queries."""
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
        """Insert a new document row right after upload (status usually 'uploaded')."""
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
        """All documents owned by this user, newest first — dashboard list."""
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
        """Fetch a document only if it belongs to owner_id — main access gate."""
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id, Document.owner_id == owner_id
            )
        )

    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Lookup by id only — caller must check ownership before returning to API."""
        return self.db.get(Document, document_id)

    def has_permission(self, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True if user has a row in document_permissions (future sharing — unused in MVP)."""
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
        """Set lifecycle status (uploaded / processing / ready / failed) and save."""
        document.status = status
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_display_name(
        self, document: Document, display_name: str
    ) -> Document:
        """Save the user-editable UI label — does not rename the file on disk."""
        document.display_name = display_name
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        """Remove the document row (chunks/messages cascade per FK rules)."""
        self.db.delete(document)
        self.db.commit()
