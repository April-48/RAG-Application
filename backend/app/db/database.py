"""Postgres engine + SessionLocal factory.

get_db() is the dependency that yields a session and closes it when done —
middleware routes use this via FastAPI Depends.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


# I yield a SQLAlchemy session for one request and close it in `finally`.
# FastAPI Depends(get_db) calls this — do not leave sessions open manually.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
