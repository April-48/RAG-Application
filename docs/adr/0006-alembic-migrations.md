# ADR 0006: Alembic migrations

## Status

Accepted (MVP)

## Context

Anyone cloning the repo should get the exact same schema.

## Decision

Run `alembic upgrade head` from `backend/`. Revisions: `0001_initial`, `0002_add_document_display_name`.

pgvector extension is created in `infra/postgres/init/` on first Docker volume init.

`init_db.py` / `create_all` is for quick experiments only.

## Trade-offs

| Good | Bad |
| ---- | --- |
| Schema changes are tracked in git | Easy to forget to run migrations after pulling changes |

## Future

When there is CI, migrations would run automatically before deploy.
