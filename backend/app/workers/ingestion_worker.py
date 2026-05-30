"""
Background ingestion entrypoint — called from FastAPI BackgroundTasks today.

Opens its own DB session, loads the doc, runs document_service.ingest().
In production you'd swap BackgroundTasks for Celery/RQ workers on Redis.
"""

from __future__ import annotations

import uuid

from app.db.database import SessionLocal
from app.services.document_service import DocumentService


def ingest_document(document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    """Run ingest in a fresh session so we're not tied to the upload request."""
    db = SessionLocal()
    try:
        service = DocumentService(db)
        document = service.documents.get_owned(document_id, owner_id)
        if document is None:
            return
        service.ingest(document)
    finally:
        db.close()
