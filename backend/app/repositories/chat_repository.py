"""Chat sessions + messages persistence.

One session per (user, document). History survives page refresh.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.message import Message


class ChatRepository:
    """Read/write chat_sessions and messages for one user + document pair."""

    def __init__(self, db: Session) -> None:
        """Store the DB session this repo uses for all queries."""
        self.db = db

    def get_session(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ChatSession | None:
        """Find existing session for this user and document, or None."""
        return self.db.scalar(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.document_id == document_id,
            )
            .order_by(ChatSession.created_at.asc())
        )

    def get_or_create_session(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ChatSession:
        """Return the session for (user, doc), creating one on first message."""
        session = self.get_session(user_id=user_id, document_id=document_id)
        if session is not None:
            return session
        session = ChatSession(user_id=user_id, document_id=document_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_message(
        self,
        *,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources_json: Any | None = None,
    ) -> Message:
        """Append one chat message — assistant rows can carry sources_json citations."""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            sources_json=sources_json,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, session_id: uuid.UUID) -> list[Message]:
        """Full conversation for a session, oldest first — powers GET /history."""
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
            )
        )
