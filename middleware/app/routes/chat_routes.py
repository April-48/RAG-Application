"""Chat routes — ask (JSON or SSE stream) and load history.

ChatService does access checks, Redis cache, retrieval, LLM, and DB writes.
We translate domain errors to 404/409/502 here.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.exceptions import DocumentNotFoundError, DocumentNotReadyError, LLMError
from app.models.user import User
from app.services.chat_service import ChatService

from ..dependencies.chat_rate_limit import get_current_user_with_chat_rate_limit
from ..dependencies.get_current_user import get_current_user
from ..schemas.chat_schema import (
    AnswerResponse,
    AskRequest,
    MessageItem,
    SourceItem,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{document_id}/ask", response_model=AnswerResponse)
def ask(
    document_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user_with_chat_rate_limit),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    """One-shot RAG answer + source chunks for a document question."""
    try:
        answer, sources = ChatService(db).ask(
            user_id=current_user.id,
            document_id=document_id,
            question=payload.question,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except DocumentNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is not ready for questions yet",
        ) from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model is unavailable",
        ) from exc

    return AnswerResponse(
        answer=answer,
        sources=[SourceItem(**source) for source in sources],
    )


@router.post("/{document_id}/ask/stream")
def ask_stream(
    document_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user_with_chat_rate_limit),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of tokens, then sources, then done — same events on cache hit."""
    # Validate + save user message before streaming so 404/409 are normal HTTP errors.
    try:
        events = ChatService(db).ask_stream(
            user_id=current_user.id,
            document_id=document_id,
            question=payload.question,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except DocumentNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is not ready for questions yet",
        ) from exc

    def sse() -> Iterator[str]:
        """Wrap pipeline events as Server-Sent Events data lines."""
        try:
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
        except LLMError:
            error_event = {
                "type": "error",
                "data": "The language model is unavailable",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{document_id}/history", response_model=list[MessageItem])
def history(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageItem]:
    """Return persisted chat messages for this user + document."""
    try:
        messages = ChatService(db).get_history(
            user_id=current_user.id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc

    return [
        MessageItem(
            id=message.id,
            role=message.role,
            content=message.content,
            sources=[
                SourceItem(**source) for source in (message.sources_json or [])
            ],
            created_at=message.created_at,
        )
        for message in messages
    ]
