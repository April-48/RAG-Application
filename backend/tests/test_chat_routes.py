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


def test_clear_history_removes_saved_messages(client, db_session) -> None:
    from app.models.chat_session import ChatSession
    from app.models.message import Message

    user = signup_user(client, "history@example.com")
    token = login_token(client, user["email"])
    document = create_document_row(
        db_session,
        owner_id=uuid.UUID(user["id"]),
        status="ready",
    )
    session = ChatSession(
        user_id=uuid.UUID(user["id"]),
        document_id=document.id,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    db_session.add_all(
        [
            Message(
                session_id=session.id,
                role="user",
                content="What is the refund policy?",
            ),
            Message(
                session_id=session.id,
                role="assistant",
                content="Refunds within 30 days.",
                sources_json=[],
            ),
        ]
    )
    db_session.commit()

    response = client.delete(
        f"/chat/{document.id}/history",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 2, "cache_cleared": 0}

    history = client.get(
        f"/chat/{document.id}/history",
        headers=auth_header(token),
    )
    assert history.status_code == 200
    assert history.json() == []


def test_cross_user_clear_history_returns_404(client, db_session) -> None:
    owner = create_user(db_session, "owner-history@example.com")
    intruder = signup_user(client, "intruder-history@example.com")
    token = login_token(client, intruder["email"])
    document = create_document_row(db_session, owner_id=owner.id, status="ready")

    response = client.delete(
        f"/chat/{document.id}/history",
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
