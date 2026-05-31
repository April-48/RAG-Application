"""Database access for chat sessions and messages.

The MVP keeps one chat session per (user, document) pair. Messages append to
that session so conversation history survives a page refresh. Assistant messages
can store sources_json — the chunk citations the UI shows under each answer.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.message import Message


class ChatRepository:
    """Read and write chat_sessions and messages for one user + document."""

    def __init__(self, db: Session) -> None:
        """Store the DB session used for every query in this repository."""
        self.db = db

    def get_session(
        self, *, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> ChatSession | None:
        """Find an existing session for this user chatting about this document.

        Returns None when the user has never asked a question on this doc yet.
        """
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
        """Return the session for (user, doc), creating one on the first message.

        ChatService calls this at the start of every ask() so the user question
        can be saved before retrieval runs.
        """
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
        """Append one chat line to a session.

        role is 'user' or 'assistant'. Assistant rows may include sources_json
        with chunk_index, page_number, and chunk_text for citations.
        """
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
        """Return the full conversation for a session, oldest message first.

        Used by GET /history so the frontend can rebuild the chat UI on load.
        """
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
            )
        )

    def clear_messages(self, session_id: uuid.UUID) -> int:
        """Delete every message in a session — used by DELETE /history.

        Returns the number of rows removed. Returns 0 when the session had no
        messages (session row itself is kept).
        """
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
