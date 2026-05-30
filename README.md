# RAG Document Q&A App

A full-stack RAG application where users upload PDF/TXT/DOCX files, ask questions about a **selected document**, and receive answers grounded in retrieved chunks—with cited sources. This is an **MVP** built for coursework and demos; detailed design lives under [`docs/`](docs/).

## Features

- User signup/login with JWT-based authentication
- Upload PDF, TXT, and DOCX documents
- Background document ingestion with status tracking (`uploaded` → `processing` → `ready` / `failed`)
- Text chunking, embeddings, and vector search with PostgreSQL + pgvector
- Single-document chat sessions with grounded source snippets
- Streaming chat responses via SSE
- Optional Redis answer cache for repeated questions (fail-open if Redis is down)
- Owner-scoped document access — users cannot read each other's files
- Rename documents, search lists, open original uploads, deep link chat via `?doc=`

## Tech Stack

| Area | Technology |
| ---- | ---------- |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| API layer | FastAPI, Pydantic, JWT |
| Application/core layer | Python services, repositories, RAG pipeline (`app` package) |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis (optional, answer cache only) |
| Migrations | Alembic |
| Storage | Local disk (MVP); S3-compatible backend planned |
| LLM / embeddings | OpenAI-compatible chat; local MiniLM or OpenAI embeddings via env config |

## Architecture Overview

Layered layout in one repo — **logical separation**, not three deployed services in the MVP:

1. **Frontend** — React UI only; calls the API over HTTP/SSE.
2. **API layer** — FastAPI routes, JWT auth, request validation, HTTP error mapping (`middleware/app/` in the repo).
3. **Application/core layer** — models, repositories, services, storage, cache, RAG pipeline. Installed editable (`pip install -e ./backend`) and imported **in-process** by FastAPI.

This keeps local setup simple while preserving clear boundaries for future workers or service extraction.

**Full design:**

- [System Design](docs/system_design.md)
- [API Design](docs/api_design.md)
- [Architecture Decision Records](docs/adr/)

## Quick Start

**Full guide:** [Setup Guide](docs/setup.md)

**Fast path** (after Docker, Python 3.12+, Node 20):

```bash
chmod +x scripts/dev_setup.sh scripts/dev_start.sh
./scripts/dev_setup.sh          # env, docker db+redis, deps, migrations
./scripts/dev_start.sh          # FastAPI API server on :8000
```

**Second terminal — frontend:**

```bash
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Set `OPENAI_API_KEY` (or `LLM_BASE_URL` for a local server) in `.env` before chat.

**Health check:** `GET http://localhost:8000/health` → `{"status":"ok"}`

## Demo Flow

**Checklist:** [Demo Checklist](docs/engineering-notes/demo-checklist.md)

1. Sign up or log in.
2. Upload a **text-based** PDF, TXT, or DOCX (scanned PDFs need OCR — not in MVP).
3. Wait until status is `ready`.
4. Open Chat and select the document.
5. Ask a question answerable from the document; show streaming response and sources.
6. With Redis running, ask the **same question twice** to show cache hit (see checklist).
7. Optionally sign up a second user and confirm owner-scoped 404 on another user's document id.

## Engineering Docs

| Document | Purpose |
| -------- | ------- |
| [System Design](docs/system_design.md) | Architecture, data model, RAG flows |
| [API Design](docs/api_design.md) | HTTP API surface |
| [Setup Guide](docs/setup.md) | Prerequisites, env vars, commands |
| [Demo Checklist](docs/engineering-notes/demo-checklist.md) | Pre-demo self-check |
| [Known Limitations](docs/engineering-notes/known-limitations.md) | MVP boundaries |
| [Troubleshooting](docs/engineering-notes/troubleshooting.md) | Common local fixes |
| [ADRs](docs/adr/) | Why we chose this stack and scope |

**Key ADRs:**

- [0001 — Layered frontend / API / application architecture](docs/adr/0001-three-layer-architecture.md)
- [0002 — PostgreSQL + pgvector](docs/adr/0002-postgres-pgvector.md)
- [0003 — Single-document RAG scope](docs/adr/0003-single-document-rag-scope.md)
- [0004 — Background ingestion (BackgroundTasks)](docs/adr/0004-async-ingestion-backgroundtasks.md)
- [0005 — Redis answer cache](docs/adr/0005-redis-answer-cache.md)
- [0006 — Alembic migrations](docs/adr/0006-alembic-migrations.md)
- [0007 — Local storage vs S3](docs/adr/0007-local-storage-vs-s3.md)

Layer notes: [frontend](frontend/README.md) · [API layer](middleware/README.md) · [application core](backend/README.md)

## Known Limitations

This is an MVP, not a production RAG platform.

- One selected document per chat session
- Ingestion uses FastAPI `BackgroundTasks`, not a durable worker queue
- Local disk storage is not multi-instance safe
- Scanned/image-only PDFs need OCR (not implemented)
- Redis cache may serve stale answers until TTL after re-ingest
- Switching embedding dimensions requires migration and re-ingestion

**Full list:** [Known Limitations](docs/engineering-notes/known-limitations.md)

## Future Improvements

- Redis + Celery/RQ for durable ingestion
- S3-compatible object storage
- Multi-document retrieval and shared document permissions
- OCR for scanned PDFs
- Cache invalidation on re-ingest
- Rate limiting, audit logs, and stronger production controls
- CI checks for migrations and backend tests

See also scalability and production notes in [System Design](docs/system_design.md) and individual ADRs.
