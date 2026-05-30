"""Signup/login request bodies and token + user responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    """POST /auth/signup body — email + password (min 8 chars)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """POST /auth/login body — returns JWT on success."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT access token returned after login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user fields — no password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
