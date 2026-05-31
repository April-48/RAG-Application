"""Document HTTP routes — upload, list, rename, download, delete.

DocumentService owns the logic. I map domain exceptions to HTTP status codes here.
After upload I schedule ingest_document() in BackgroundTasks so the response is fast.
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
    InvalidUploadContentError,
    InvalidUploadFilenameError,
    UnsupportedFileTypeError,
    UploadTooLargeError,
)
from app.models.user import User
from app.services.document_service import DocumentService
from app.services.upload_validation import ALLOWED_EXTENSIONS
from app.workers.ingestion_worker import ingest_document

from ..dependencies.get_current_user import get_current_user
from ..schemas.document_schema import DocumentRenameRequest, DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
# POST /documents/upload — accept multipart file upload for the logged-in user.
# DocumentService saves bytes to disk and creates a row with status "uploaded".
# I schedule ingest_document() in BackgroundTasks so this handler returns fast.
# Return DocumentResponse with HTTP 201.
# Return HTTP 400 for missing filename, bad extension, or content mismatch.
# Return HTTP 413 when the file exceeds MAX_UPLOAD_SIZE_MB.
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
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
    except InvalidUploadFilenameError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc) or "Invalid filename",
        ) from exc
    except InvalidUploadContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(ingest_document, document.id, current_user.id)
    return document


@router.get("", response_model=list[DocumentResponse])
# GET /documents — list every document owned by the current user.
# DocumentService.list_documents returns rows newest-first for the dashboard.
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    return DocumentService(db).list_documents(current_user.id)


@router.get("/{document_id}", response_model=DocumentResponse)
# GET /documents/{document_id} — fetch one owned document by id.
# Return DocumentResponse on success.
# Return HTTP 404 if the id does not exist or belongs to another user.
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        return DocumentService(db).get_document(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@router.patch("/{document_id}", response_model=DocumentResponse)
# PATCH /documents/{document_id} — rename the UI label (display_name).
# The original filename on disk does not change.
# Return HTTP 404 if the document is missing or not owned by this user.
def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        return DocumentService(db).rename_document(
            document_id, current_user.id, body.display_name
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@router.get("/{document_id}/file")
# GET /documents/{document_id}/file — download or open the original upload.
# DocumentService resolves the path after an owner check.
# Return a FileResponse stream; never expose storage_path in JSON.
# Return HTTP 404 if the doc is missing, not owned, or the file vanished from disk.
def get_document_file(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
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
# DELETE /documents/{document_id} — remove an owned document.
# DocumentService deletes the DB row (chunks and messages cascade) and wipes disk files.
# Return HTTP 204 with an empty body on success.
# Return HTTP 404 if the document is missing or not owned by this user.
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        DocumentService(db).delete_document(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
