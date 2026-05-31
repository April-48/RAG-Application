"""Document DB queries — always filtered by owner_id when it matters.

Repository layer = raw SQLAlchemy, no business rules. Services call us.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_permission import DocumentPermission


# CRUD and owner-scoped lookups for the documents table.
class DocumentRepository:

    # Store the DB session this repo uses for every query.
    def __init__(self, db: Session) -> None:
        self.db = db

    # Insert a new document row right after upload.
    # Status is usually 'uploaded' until background ingestion runs.
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

    # List all documents owned by this user, newest first — dashboard view.
    def list_by_owner(self, owner_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.scalars(
                select(Document)
                .where(Document.owner_id == owner_id)
                .order_by(Document.created_at.desc())
            )
        )

    # Fetch a document only if it belongs to owner_id — main access gate.
    # Output: Document row or None when id exists but owner differs.
    def get_owned(
        self, document_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Document | None:
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id, Document.owner_id == owner_id
            )
        )

    # Lookup by id only — caller must verify ownership before exposing to API.
    def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.db.get(Document, document_id)

    # True if user has a row in document_permissions (future sharing — MVP unused).
    def has_permission(self, document_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (
            self.db.scalar(
                select(DocumentPermission.id).where(
                    DocumentPermission.document_id == document_id,
                    DocumentPermission.user_id == user_id,
                )
            )
            is not None
        )

    # Set lifecycle status (uploaded / processing / ready / failed) and save.
    def update_status(self, document: Document, status: str) -> Document:
        document.status = status
        self.db.commit()
        self.db.refresh(document)
        return document

    # Save the user-editable display name — does not rename the file on disk.
    def update_display_name(
        self, document: Document, display_name: str
    ) -> Document:
        document.display_name = display_name
        self.db.commit()
        self.db.refresh(document)
        return document

    # Remove the document row — chunks and messages cascade per FK rules.
    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()
