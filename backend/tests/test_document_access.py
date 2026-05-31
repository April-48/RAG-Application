"""Document ownership and upload validation tests."""

from __future__ import annotations

import uuid
from pathlib import Path
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import DocumentNotFoundError, UnsupportedFileTypeError
from app.services.document_service import DocumentService
from app.storage.base import StorageBackend

from tests.conftest import (
    auth_header,
    create_document_row,
    create_user,
    login_token,
    signup_user,
)


class FakeStorage(StorageBackend):
    """Minimal storage backend for service-level tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self,
        *,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        fileobj,
    ) -> str:
        rel = f"{user_id}/{document_id}/{filename}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fileobj.read())
        return rel

    def full_path(self, storage_path: str) -> Path:
        return self.root / storage_path

    def delete_document(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> None:
        target = self.root / str(user_id) / str(document_id)
        if target.exists():
            for child in target.iterdir():
                child.unlink()
            target.rmdir()


def test_unsupported_file_type_rejected(client) -> None:
    token = login_token(client, signup_user(client, "u1@example.com")["email"])
    response = client.post(
        "/documents/upload",
        headers=auth_header(token),
        files={"file": ("report.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_unsupported_file_type_raises_in_service(db_session, tmp_path) -> None:
    user = create_user(db_session, "svc@example.com")
    service = DocumentService(db_session, storage=FakeStorage(tmp_path))
    with pytest.raises(UnsupportedFileTypeError):
        service.upload(
            owner_id=user.id,
            filename="bad.bin",
            fileobj=BytesIO(b"x"),
        )


def test_list_documents_only_returns_current_user(client, db_session) -> None:
    user_a = signup_user(client, "owner-a@example.com")
    token_a = login_token(client, "owner-a@example.com")
    user_b = create_user(db_session, "owner-b@example.com")

    doc_a = create_document_row(db_session, owner_id=uuid.UUID(user_a["id"]))
    create_document_row(db_session, owner_id=user_b.id, filename="secret.txt")

    response = client.get("/documents", headers=auth_header(token_a))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(doc_a.id) in ids
    assert len(ids) == 1


def test_user_cannot_access_other_users_document(client, db_session) -> None:
    owner = create_user(db_session, "owner@example.com")
    intruder = signup_user(client, "intruder@example.com")
    token = login_token(client, intruder["email"])
    document = create_document_row(db_session, owner_id=owner.id)

    response = client.get(
        f"/documents/{document.id}",
        headers=auth_header(token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_user_cannot_download_other_users_file(client, db_session) -> None:
    owner = create_user(db_session, "file-owner@example.com")
    token = login_token(client, signup_user(client, "file-intruder@example.com")["email"])
    document = create_document_row(
        db_session,
        owner_id=owner.id,
        filename="private.txt",
        storage_path="ignored/on/disk.txt",
    )

    response = client.get(
        f"/documents/{document.id}/file",
        headers=auth_header(token),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_get_accessible_document_hides_other_owner(db_session) -> None:
    owner = create_user(db_session, "hidden@example.com")
    other = create_user(db_session, "other@example.com")
    document = create_document_row(db_session, owner_id=owner.id)
    service = DocumentService(db_session, storage=FakeStorage(Path("/tmp/unused")))

    with pytest.raises(DocumentNotFoundError):
        service.get_accessible_document(document.id, other.id)
