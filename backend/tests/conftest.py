"""Shared pytest fixtures — in-memory SQLite for auth/document route tests."""

from __future__ import annotations

import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.database import get_db  # noqa: E402
from app.models.chat_session import ChatSession  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.document_permission import DocumentPermission  # noqa: E402
from app.models.message import Message  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """SQLite session with users + documents tables only (no pgvector)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    Document.__table__.create(engine)
    DocumentPermission.__table__.create(engine)
    ChatSession.__table__.create(engine)
    Message.__table__.create(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        DocumentPermission.__table__.drop(engine)
        Document.__table__.drop(engine)
        Message.__table__.drop(engine)
        ChatSession.__table__.drop(engine)
        User.__table__.drop(engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to the in-memory session."""
    from middleware.app.main import app

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def signup_user(
    client: TestClient,
    email: str,
    password: str = "password123",
) -> dict:
    """Register via API and return the JSON user body."""
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_token(
    client: TestClient,
    email: str,
    password: str = "password123",
) -> str:
    """Login and return the bearer access token."""
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    """Authorization header for protected routes."""
    return {"Authorization": f"Bearer {token}"}


def create_document_row(
    db: Session,
    *,
    owner_id: uuid.UUID,
    filename: str = "notes.txt",
    status: str = "ready",
    storage_path: str = "fake/path/notes.txt",
) -> Document:
    """Insert a document row directly (skips file upload / ingestion)."""
    document = Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        filename=filename,
        file_type=Path(filename).suffix.lstrip(".") or "txt",
        storage_path=storage_path,
        visibility="private",
        status=status,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_user(db: Session, email: str, password: str = "password123") -> User:
    """Create a user through AuthService (hashed password)."""
    return AuthService(db).signup(email, password)
