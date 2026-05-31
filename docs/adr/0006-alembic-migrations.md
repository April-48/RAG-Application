# ADR 0006: Alembic for database migrations

## Status

Accepted (MVP)

## Context

The schema has users, documents, pgvector chunks, chat tables, `document_permissions`, and optional `display_name` (migration 0002). Teammates and graders need the same Postgres shape from git — not manual DDL on each laptop.

## Decision

Use **Alembic** under `backend/alembic/` as the main schema path.

- Run `alembic upgrade head` from `backend/` (also in `scripts/dev_setup.sh`).
- Revisions: `0001_initial`, `0002_add_document_display_name`.
- `env.py` reads `DATABASE_URL` and imports all ORM models.

`backend/app/db/init_db.py` (`create_all`) is for **quick local experiments only**, not the documented setup path.

**pgvector extension:** In Docker, created by `infra/postgres/init/001_extensions.sql` on first volume init, before Alembic creates `Vector(384)` columns. Alembic could run `CREATE EXTENSION` in a migration — we use init SQL for fresh Docker DBs.

**Caveat:** Init scripts run **only on first volume creation**. An old volume without the extension needs `docker compose down -v` and a fresh migrate (see setup troubleshooting).

## Alternatives considered

- **`create_all` only** — no history; painful when adding columns.
- **Hand-written SQL** — easy to drift from models.
- **Another migration tool** — stack is already SQLAlchemy + Alembic.

## Why this works

- One command after Postgres is up.
- Easy to explain versioned schema changes in interviews.
- Embedding dimension changes belong in an explicit migration (ADR 0002).
- No surprise DDL on API startup.

## Limits

- Run migrations after pulling new revisions.
- `downgrade` exists for dev; no formal production rollback policy in MVP.

## Future improvements

- CI step: `alembic upgrade head` on ephemeral Postgres.
- Runbook when changing `Vector(n)`.
- Optionally move `CREATE EXTENSION` into Alembic for non-Docker setups.
