"""Alembic migration runner — reads DATABASE_URL and imports all ORM models."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# So `from app.models import ...` works when you run alembic from backend/
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401  (import registers all tables on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL from env, or fall back to app settings (docker-compose default).
database_url = os.getenv("DATABASE_URL") or get_settings().database_url
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print SQL to stdout without connecting — useful for reviewing migrations."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live Postgres connection (normal `alembic upgrade`)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
