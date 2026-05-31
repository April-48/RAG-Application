"""
Background ingestion entrypoint — called from FastAPI BackgroundTasks today.

Opens its own DB session, loads the doc, runs document_service.ingest().
In production you'd swap BackgroundTasks for Celery/RQ workers on Redis.
"""

from __future__ import annotations

import uuid

from app.db.database import SessionLocal
from app.services.document_service import DocumentService


# I run full ingestion in a fresh DB session after upload returns.
# Input: document_id and owner_id from the upload handler.
# I no-op if the document row is missing or not owned by owner_id.
def ingest_document(document_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        service = DocumentService(db)
        document = service.documents.get_owned(document_id, owner_id)
        if document is None:
            return
        service.ingest(document)
    finally:
        db.close()
