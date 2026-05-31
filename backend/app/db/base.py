"""SQLAlchemy Base — every ORM model subclasses this.

Import app.models before migrations so all tables register on Base.metadata.
"""

from sqlalchemy.orm import DeclarativeBase


# I subclass this for every ORM model so Alembic sees one metadata registry.
class Base(DeclarativeBase):
    pass
