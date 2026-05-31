"""Chat sessions + messages persistence.

One session per (user, document). History survives page refresh.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.message import Message


# Read/write chat_sessions and messages for one user + document pair.
class ChatRepository:

    # Store the DB session this repo uses for every query.
    def __init__(self, db: Session) -> None:
        self.db = db

    # Find an existing session for this user and document.
    # Output: ChatSession row or None if no conversation started yet.
    def get_session(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ChatSession | None:
        return self.db.scalar(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.document_id == document_id,
            )
            .order_by(ChatSession.created_at.asc())
        )

    # Return the session for (user, doc), creating one on the first message.
    def get_or_create_session(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ChatSession:
        session = self.get_session(user_id=user_id, document_id=document_id)
        if session is not None:
            return session
        session = ChatSession(user_id=user_id, document_id=document_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    # Append one chat message to a session.
    # Assistant rows may carry sources_json with chunk citations.
    def add_message(
        self,
        *,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources_json: Any | None = None,
    ) -> Message:
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

    # List the full conversation for a session, oldest first — GET /history.
    def list_messages(self, session_id: uuid.UUID) -> list[Message]:
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
            )
        )

    # Delete every message in a session — DELETE /history.
    # Output: number of rows removed (0 when the session had no messages).
    def clear_messages(self, session_id: uuid.UUID) -> int:
        count = self.db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == session_id)
        )
        deleted = int(count or 0)
        if deleted == 0:
            return 0
        self.db.execute(delete(Message).where(Message.session_id == session_id))
        self.db.commit()
        return deleted
