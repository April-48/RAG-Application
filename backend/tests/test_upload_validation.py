"""Tests for upload size, content, and filename validation."""

from __future__ import annotations

import io
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.exceptions import (
    InvalidUploadContentError,
    UploadTooLargeError,
)
from app.services.document_service import DocumentService
from app.services.upload_validation import (
    read_upload_bytes,
    sanitize_upload_filename,
    validate_upload_content,
)
from app.storage.base import StorageBackend

from tests.conftest import auth_header, create_user, login_token, signup_user

MINIMAL_PDF = b"%PDF-1.4\n%%EOF\n"
MINIMAL_TXT = b"hello world\n"


def make_minimal_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
    return buf.getvalue()


class FakeStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.last_saved_name: str | None = None

    def save(self, *, user_id, document_id, filename, fileobj) -> str:
        self.last_saved_name = filename
        rel = f"{user_id}/{document_id}/{filename}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fileobj.read())
        return rel

    def full_path(self, storage_path: str) -> Path:
        return self.root / storage_path

    def delete_document(self, *, user_id, document_id) -> None:
        target = self.root / str(user_id) / str(document_id)
        if target.exists():
            for child in target.iterdir():
                child.unlink()
            target.rmdir()


def test_validate_pdf_header() -> None:
    validate_upload_content(".pdf", MINIMAL_PDF)


def test_validate_pdf_rejects_exe_bytes() -> None:
    with pytest.raises(InvalidUploadContentError, match="PDF"):
        validate_upload_content(".pdf", b"MZfake executable")


def test_validate_docx_requires_content_types() -> None:
    validate_upload_content(".docx", make_minimal_docx())


def test_validate_docx_rejects_bad_zip() -> None:
    with pytest.raises(InvalidUploadContentError, match="DOCX"):
        validate_upload_content(".docx", b"not a zip file")


def test_validate_docx_rejects_zip_without_content_types() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", "<doc/>")
    with pytest.raises(InvalidUploadContentError, match="Content_Types"):
        validate_upload_content(".docx", buf.getvalue())


def test_validate_txt_utf8() -> None:
    validate_upload_content(".txt", MINIMAL_TXT)


def test_validate_txt_rejects_invalid_utf8() -> None:
    with pytest.raises(InvalidUploadContentError, match="UTF-8"):
        validate_upload_content(".txt", b"\xff\xfe")


def test_read_upload_bytes_enforces_limit() -> None:
    with pytest.raises(UploadTooLargeError):
        read_upload_bytes(BytesIO(b"x" * 11), max_bytes=10)


def test_sanitize_strips_path_traversal() -> None:
    assert sanitize_upload_filename("../../evil.pdf", ".pdf") == "evil.pdf"


def test_sanitize_replaces_unsafe_chars() -> None:
    name = sanitize_upload_filename('rep"ort|bad.pdf', ".pdf")
    assert '"' not in name
    assert "|" not in name
    assert name.endswith(".pdf")


@patch("app.services.document_service.get_settings")
def test_service_rejects_oversized_upload(mock_settings, db_session, tmp_path) -> None:
    mock_settings.return_value = Settings(max_upload_size_mb=1)
    user = create_user(db_session, "big@example.com")
    service = DocumentService(db_session, storage=FakeStorage(tmp_path))
    payload = b"x" * (1024 * 1024 + 1)

    with pytest.raises(UploadTooLargeError):
        service.upload(
            owner_id=user.id,
            filename="big.txt",
            fileobj=BytesIO(payload),
        )


@patch("app.services.document_service.get_settings")
def test_service_stores_document_id_on_disk(mock_settings, db_session, tmp_path) -> None:
    mock_settings.return_value = Settings(max_upload_size_mb=20)
    user = create_user(db_session, "disk@example.com")
    storage = FakeStorage(tmp_path)
    service = DocumentService(db_session, storage=storage)

    document = service.upload(
        owner_id=user.id,
        filename="../../notes.txt",
        fileobj=BytesIO(MINIMAL_TXT),
    )

    assert document.filename == "notes.txt"
    assert storage.last_saved_name == f"{document.id}.txt"


def test_upload_exe_rejected(client) -> None:
    token = login_token(client, signup_user(client, "exe@example.com")["email"])
    response = client.post(
        "/documents/upload",
        headers=auth_header(token),
        files={"file": ("report.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_exe_renamed_to_pdf_rejected(client) -> None:
    token = login_token(client, signup_user(client, "fakepdf@example.com")["email"])
    response = client.post(
        "/documents/upload",
        headers=auth_header(token),
        files={"file": ("report.pdf", b"MZfake", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_valid_pdf_accepted(client) -> None:
    signup_user(client, "pdf@example.com")
    token = login_token(client, "pdf@example.com")
    with patch("middleware.app.routes.document_routes.ingest_document"):
        response = client.post(
            "/documents/upload",
            headers=auth_header(token),
            files={"file": ("paper.pdf", MINIMAL_PDF, "application/pdf")},
        )
    assert response.status_code == 201
    assert response.json()["filename"] == "paper.pdf"


def test_upload_path_traversal_filename_sanitized(client) -> None:
    signup_user(client, "traversal@example.com")
    token = login_token(client, "traversal@example.com")

    with patch("middleware.app.routes.document_routes.ingest_document"):
        response = client.post(
            "/documents/upload",
            headers=auth_header(token),
            files={"file": ("../../evil.pdf", MINIMAL_PDF, "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json()["filename"] == "evil.pdf"


@patch("app.services.document_service.get_settings")
def test_upload_oversized_returns_413(mock_settings, client) -> None:
    mock_settings.return_value = Settings(max_upload_size_mb=1)
    signup_user(client, "413@example.com")
    token = login_token(client, "413@example.com")
    payload = b"x" * (1024 * 1024 + 1)

    response = client.post(
        "/documents/upload",
        headers=auth_header(token),
        files={"file": ("big.txt", payload, "text/plain")},
    )
    assert response.status_code == 413
    assert "maximum upload size" in response.json()["detail"].lower()
