"""Request/response models for chat — question in, answer + sources out."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """POST /chat/{document_id}/ask body — the user's question."""

    question: str = Field(min_length=1, max_length=4000)


class SourceItem(BaseModel):
    """One cited chunk shown in the Sources panel."""

    chunk_index: int
    page_number: int | None
    chunk_text: str


class AnswerResponse(BaseModel):
    """Non-streaming chat response — full answer plus source list."""

    answer: str
    sources: list[SourceItem]


class MessageItem(BaseModel):
    """One row from chat history — user or assistant, maybe with citation sources."""

    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceItem] = Field(default_factory=list)
    created_at: datetime
