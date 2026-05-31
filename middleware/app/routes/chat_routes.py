"""Chat HTTP routes — one-shot ask, SSE stream, and history.

ChatService runs cache, retrieval, LLM, and DB writes. I translate domain errors to HTTP codes here.
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
    ClearHistoryResponse,
    MessageItem,
    SourceItem,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{document_id}/ask", response_model=AnswerResponse)
# POST /chat/{document_id}/ask — one-shot RAG answer plus source chunks.
# Depends on get_current_user_with_chat_rate_limit (auth + Redis cap).
# ChatService checks cache, runs hybrid retrieval, calls the LLM when needed,
# saves user and assistant messages, and may write Redis cache.
# Return AnswerResponse JSON on success.
# Map DocumentNotFoundError -> 404, DocumentNotReadyError -> 409, LLMError -> 502.
def ask(
    document_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user_with_chat_rate_limit),
    db: Session = Depends(get_db),
) -> AnswerResponse:
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
# POST /chat/{document_id}/ask/stream — same RAG flow as /ask but over SSE.
# ChatService.ask_stream yields dict events: token, sources, done (or error on LLM fail).
# I validate access before opening the stream so 404/409 are normal HTTP errors.
# Rate limit applies via get_current_user_with_chat_rate_limit.
def ask_stream(
    document_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user_with_chat_rate_limit),
    db: Session = Depends(get_db),
) -> StreamingResponse:
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

    # Inner generator: wrap each ChatService event dict as one SSE "data:" line.
    # If the LLM throws mid-stream, emit one error event instead of dropping the connection.
    def sse() -> Iterator[str]:
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
# GET /chat/{document_id}/history — load saved messages for this user + document.
# ChatService checks document access first, then reads chat_sessions / messages.
# Return an empty list if no conversation exists yet.
# Return HTTP 404 if the document is missing or not accessible.
def history(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageItem]:
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


@router.delete("/{document_id}/history", response_model=ClearHistoryResponse)
# DELETE /chat/{document_id}/history — remove all saved messages for this user + doc.
# ChatService checks document access first, then deletes rows in chat_sessions / messages.
# Return deleted=0 when no conversation exists yet.
# Return HTTP 404 if the document is missing or not accessible.
def clear_history(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClearHistoryResponse:
    try:
        result = ChatService(db).clear_history(
            user_id=current_user.id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc

    return ClearHistoryResponse(
        deleted=result.deleted, cache_cleared=result.cache_cleared
    )
