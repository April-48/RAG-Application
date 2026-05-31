"""Pydantic models for /auth request and response bodies."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Request body for POST /auth/signup.
# email must be a valid address; password is 8 to 128 characters.
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# Request body for POST /auth/login.
# FastAPI validates the shape before AuthService checks the password hash.
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# Response body after a successful login.
# The frontend stores access_token and sends Authorization: Bearer on later calls.
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Public user fields returned by signup and GET /auth/me.
# I never include password_hash in API JSON.
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
