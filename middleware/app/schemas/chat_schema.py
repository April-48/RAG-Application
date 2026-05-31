"""Pydantic models for /chat ask, stream, and history responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# Request body for POST /chat/{document_id}/ask and /ask/stream.
# question is required, 1 to 4000 characters.
class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


# One cited chunk shown in the Sources panel.
# page_number is set for PDF chunks; null for TXT/DOCX.
class SourceItem(BaseModel):
    chunk_index: int
    page_number: int | None
    chunk_text: str


# JSON response for non-streaming POST /chat/{document_id}/ask.
# sources come from retrieval, not from parsing the LLM output.
class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    retrieval_mode: str | None = None
    retrieval_page: int | None = None
    retrieval_section: str | None = None


# One message row returned by GET /chat/{document_id}/history.
# Assistant rows may include sources; user rows usually have an empty sources list.
class MessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceItem] = Field(default_factory=list)
    retrieval_mode: str | None = None
    retrieval_page: int | None = None
    retrieval_section: str | None = None
    created_at: datetime


# Response for DELETE /chat/{document_id}/history.
class ClearHistoryResponse(BaseModel):
    deleted: int
    cache_cleared: int = 0
