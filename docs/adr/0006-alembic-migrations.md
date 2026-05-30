# ADR 0006: Alembic for database schema migrations

## Status

Accepted (MVP)

## Context

The schema includes users, documents, pgvector chunks, chat tables, a stub `document_permissions` table (in `0001_initial`), and optional `display_name` (added in `0002_add_document_display_name`). Teammates and graders need the same Postgres shape from git, not ad-hoc DDL on each laptop.

## Decision

Use **Alembic** under `backend/alembic/` as the **canonical** schema path.

- Run `alembic upgrade head` from `backend/` (also in `scripts/dev_setup.sh`).
- Revisions in `backend/alembic/versions/` — currently `0001_initial` and `0002_add_document_display_name`.
- `env.py` reads `DATABASE_URL` and imports all ORM models so metadata is complete.

`backend/app/db/init_db.py` (`create_all`) is for **throwaway local experiments only**, not the primary setup path documented in `docs/setup.md`.

**pgvector extension (this project’s Docker setup):** For the MVP Compose flow, the extension is created by `infra/postgres/init/001_extensions.sql` when the Postgres **volume is first initialized**, before `alembic upgrade head` creates tables with `Vector(384)` columns. Alembic *could* run `CREATE EXTENSION IF NOT EXISTS vector;` in a migration — we simply chose init SQL for fresh Docker databases. Migration `0001` does not create the extension itself.

**Docker init caveat:** Init scripts run **only on first volume creation**. If an old local volume exists without the extension, fixing init SQL alone will not re-run automatically — you may need `docker compose down -v` and a fresh migrate (see `docs/setup.md` troubleshooting).

## Alternatives Considered

- **`create_all` only** — fast initially, no version history; painful when adding columns like `display_name`.
- **Hand-written SQL scripts** — easy to drift from SQLAlchemy models.
- **Another migration tool** — stack is already SQLAlchemy + Alembic.

## Rationale

- **Reproducible homework setup** — one command after Postgres is up.
- **Interview familiarity** — versioned schema changes are easy to explain.
- **Tied to ADR 0002** — embedding dimension changes belong in an explicit migration plus re-ingest, not silent drift.
- **No surprise DDL on API startup** — migrations are deliberate, not automatic when uvicorn starts.

## Consequences

**Benefits**

- Schema changes are reviewed in git like application code.
- `0002` shows how to evolve the MVP without resetting the whole database.

**Limitations**

- Contributors must run migrations after pulling new revisions.
- `downgrade` exists for dev rollback; a formal production rollback policy is out of MVP scope.

## Future Improvements

- CI step: `alembic upgrade head` against ephemeral Postgres.
- Runbook when changing `Vector(n)` (coordinate with ADR 0002).
- Optionally move `CREATE EXTENSION` into Alembic if we need non-Docker environments without init SQL.
