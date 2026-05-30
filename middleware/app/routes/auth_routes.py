"""Auth routes — signup, login, GET /me.

Schemas validate the body; AuthService does hashing + JWT. No DB code here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.exceptions import EmailAlreadyExistsError, InvalidCredentialsError
from app.models.user import User
from app.services.auth_service import AuthService

from ..dependencies.get_current_user import get_current_user
from ..schemas.auth_schema import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    """Register a new user — 409 if email already exists."""
    try:
        return AuthService(db).signup(payload.email, payload.password)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Verify credentials and return a JWT access token."""
    try:
        token, _ = AuthService(db).login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user from the Bearer token."""
    return current_user
