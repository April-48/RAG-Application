"""HTTP tests for chat routes — access control and document readiness."""

from __future__ import annotations

import uuid

from tests.conftest import (
    auth_header,
    create_document_row,
    create_user,
    login_token,
    signup_user,
)


def test_cross_user_chat_ask_returns_404(client, db_session) -> None:
    owner = create_user(db_session, "owner@example.com")
    intruder = signup_user(client, "intruder@example.com")
    token = login_token(client, intruder["email"])
    document = create_document_row(db_session, owner_id=owner.id, status="ready")

    response = client.post(
        f"/chat/{document.id}/ask",
        headers=auth_header(token),
        json={"question": "What is in this document?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_ask_on_non_ready_document_returns_409(client, db_session) -> None:
    user = signup_user(client, "asker@example.com")
    token = login_token(client, user["email"])
    document = create_document_row(
        db_session,
        owner_id=uuid.UUID(user["id"]),
        status="processing",
    )

    response = client.post(
        f"/chat/{document.id}/ask",
        headers=auth_header(token),
        json={"question": "Summarize this document."},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Document is not ready for questions yet"
