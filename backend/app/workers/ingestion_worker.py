"""
Background ingestion entrypoint — runs after upload returns to the user.

Today FastAPI BackgroundTasks call ingest_document() in the same process.
The upload handler saves the file, creates a DB row with status "uploaded",
then schedules this function. It opens its own DB session (separate from the
request session), loads the document, and runs DocumentService.ingest().

In production you would swap BackgroundTasks for Celery/RQ workers on Redis,
but the ingest_document() signature can stay the same.
"""

from __future__ import annotations

import uuid

from app.db.database import SessionLocal
from app.services.document_service import DocumentService


def ingest_document(document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    """Run full parse → chunk → embed → save for one uploaded document.

    I open a fresh SessionLocal because BackgroundTasks run after the HTTP
    request ends and the request-scoped session is already closed.

    Silently returns when the document row is missing or not owned by owner_id
    (stale task after delete, or wrong id). On success status becomes "ready";
    on failure it becomes "failed" and partial chunks are cleaned up.
    """
    db = SessionLocal()
    try:
        service = DocumentService(db)
        document = service.documents.get_owned(document_id, owner_id)
        if document is None:
            return
        service.ingest(document)
    finally:
        db.close()
