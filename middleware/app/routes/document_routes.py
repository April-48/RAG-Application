"""Document API routes — upload, list, rename, download, delete.

All the real logic is in DocumentService. We just auth the user, map exceptions
to HTTP codes, and kick off background ingestion after upload.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.exceptions import (
    DocumentFileNotFoundError,
    DocumentNotFoundError,
    UnsupportedFileTypeError,
)
from app.models.user import User
from app.services.document_service import ALLOWED_EXTENSIONS, DocumentService
from app.workers.ingestion_worker import ingest_document

from ..dependencies.get_current_user import get_current_user
from ..schemas.document_schema import DocumentRenameRequest, DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Upload a file — returns immediately; ingestion runs in BackgroundTasks."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
        )
    try:
        document = DocumentService(db).upload(
            owner_id=current_user.id, filename=file.filename, fileobj=file.file
        )
    except UnsupportedFileTypeError as exc:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {allowed}",
        ) from exc

    # Return right away with status "uploaded"; worker flips to ready/failed later.
    background_tasks.add_task(ingest_document, document.id, current_user.id)
    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents owned by the current user."""
    return DocumentService(db).list_documents(current_user.id)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Get one owned document by id — 404 if missing or not yours."""
    try:
        return DocumentService(db).get_document(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@router.patch("/{document_id}", response_model=DocumentResponse)
def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Update display_name (UI label only — file on disk unchanged)."""
    try:
        return DocumentService(db).rename_document(
            document_id, current_user.id, body.display_name
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@router.get("/{document_id}/file")
def get_document_file(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Stream the original uploaded file after owner check — never exposes storage_path."""
    try:
        path, media_type, filename = DocumentService(db).get_original_file(
            document_id, current_user.id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except DocumentFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file not found on server",
        ) from exc

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete document row, chunks, and files on disk for an owned document."""
    try:
        DocumentService(db).delete_document(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
