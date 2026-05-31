"""Dev-only helper: create_all tables from ORM models.

For local hacking only — real schema changes should go through Alembic migrations.
Run: python -m app.db.init_db (from backend/ on PYTHONPATH)
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.base import Base
from app.db.database import engine

import app.models  # noqa: F401  (import registers all tables on Base.metadata)


# I create every table registered on Base.metadata via SQLAlchemy create_all.
# Use this for local dev only — production schema changes go through Alembic.
def init_db() -> None:
    Base.metadata.create_all(bind=engine)


# CLI entry point: run create_all and print the table names I created.
def main() -> None:
    print("Creating database tables...")
    init_db()
    print("Done. Created tables:")
    for table_name in sorted(Base.metadata.tables):
        print(f"  - {table_name}")


if __name__ == "__main__":
    main()
