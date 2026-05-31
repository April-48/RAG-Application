"""Auth HTTP routes — signup, login, and GET /me.

Pydantic schemas validate the body. AuthService handles hashing and JWT. No SQL here.
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
# POST /auth/signup — create a new account from email + password.
# AuthService hashes the password with bcrypt and inserts a User row.
# Return UserResponse (id, email, created_at) with HTTP 201 on success.
# Return HTTP 409 if that email is already registered.
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    try:
        return AuthService(db).signup(payload.email, payload.password)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try logging in instead.",
        ) from exc


@router.post("/login", response_model=TokenResponse)
# POST /auth/login — verify email and password, then mint a JWT.
# AuthService.authenticate checks the bcrypt hash.
# Return {"access_token": "...", "token_type": "bearer"} on success.
# Return HTTP 401 for wrong email or password (same error message either way).
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token, _ = AuthService(db).login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
# GET /auth/me — return the User for the Bearer token on this request.
# Depends on get_current_user, so missing or bad tokens become HTTP 401.
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
