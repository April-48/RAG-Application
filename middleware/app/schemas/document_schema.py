"""Pydantic models for /documents responses and rename requests.

I never expose storage_path — that path is server-internal only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# One document row as the frontend sees it after upload or list/get.
# Includes status (uploaded / processing / ready / failed) but not storage_path.
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    filename: str
    display_name: str | None
    file_type: str | None
    visibility: str
    status: str
    created_at: datetime
    updated_at: datetime


# Request body for PATCH /documents/{document_id}.
# display_name is the UI label only; the file on disk keeps its original name.
class DocumentRenameRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)

    # Trim leading/trailing whitespace before saving display_name.
    # Reject empty strings so the UI never shows a blank label.
    @field_validator("display_name")
    @classmethod
    def strip_and_validate_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("display_name must not be empty")
        return trimmed
