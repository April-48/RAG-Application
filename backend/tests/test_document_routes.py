"""HTTP tests for document upload and rename routes."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from tests.conftest import (
    auth_header,
    create_document_row,
    login_token,
    signup_user,
)


def test_upload_valid_txt_returns_201(client) -> None:
    signup_user(client, "upload@example.com")
    token = login_token(client, "upload@example.com")

    with patch("middleware.app.routes.document_routes.ingest_document"):
        response = client.post(
            "/documents/upload",
            headers=auth_header(token),
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["status"] == "uploaded"
    assert body["file_type"] == "txt"


def test_rename_document_updates_display_name(client, db_session) -> None:
    user = signup_user(client, "rename@example.com")
    token = login_token(client, "rename@example.com")
    document = create_document_row(db_session, owner_id=uuid.UUID(user["id"]))

    response = client.patch(
        f"/documents/{document.id}",
        headers=auth_header(token),
        json={"display_name": "My Notes"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "My Notes"
