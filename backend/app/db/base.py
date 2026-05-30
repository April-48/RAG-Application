"""SQLAlchemy Base — every ORM model subclasses this.

Import app.models before migrations so all tables register on Base.metadata.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass
