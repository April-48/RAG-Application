"""Pydantic shapes for document endpoints — what the frontend sees.

We never expose storage_path; that's internal server layout only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentResponse(BaseModel):
    """One document as the API returns it — status, names, no storage_path."""

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


class DocumentRenameRequest(BaseModel):
    """PATCH /documents/{id} body — new display_name for the UI."""

    display_name: str = Field(..., min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def strip_and_validate_display_name(cls, value: str) -> str:
        """Trim whitespace and reject empty labels after strip."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("display_name must not be empty")
        return trimmed
