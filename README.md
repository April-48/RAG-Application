# RAG Document Q&A App

This is a full-stack RAG web app for a homework project. Users can upload PDF, TXT, or DOCX files, pick one document, ask questions about it, and get AI answers backed by retrieved text chunks. The UI also shows source snippets so you can see where the answer came from.

This version runs locally with Docker Compose. It is an **MVP**, not a production system — but the code is split into frontend, API, and backend layers so it is easier to explain and extend later.

> Even though everything runs on one laptop today, the project separates the UI, API, database, cache, file storage, and RAG logic. That makes it possible to scale the API, move ingestion to workers, switch to S3 storage, or upgrade vector search later.

## Features

- Sign up and log in with JWT
- Upload PDF, TXT, and DOCX files
- Background ingestion with status tracking (`uploaded` → `processing` → `ready` / `failed`)
- Text chunking, embeddings, and **hybrid RAG retrieval** (rule-based query router + pgvector search)
- Single-document chat with source snippets
- Streaming chat answers over SSE
- Optional Redis answer cache for repeat questions (app still works if Redis is down)
- Optional Redis chat rate limit on ask routes (10/min per user; also fail-open)
- Owner-only document access — users cannot read each other's files
- Rename documents, search the list, open original uploads, deep link chat with `?doc=`

## Tech Stack

| Area | Technology |
| ---- | ---------- |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| API layer | FastAPI, Pydantic, JWT |
| Backend / core | Python services, repositories, RAG pipeline (`app` package) |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis (optional answer cache + chat rate limit) |
| Migrations | Alembic |
| Storage | Local disk for MVP; S3-style backend planned |
| LLM / embeddings | OpenAI-compatible chat; local MiniLM or OpenAI embeddings via env config |

## Architecture Overview

The repo has three logical layers. In the MVP they mostly run in one Python process, but the folders are separated on purpose:

1. **Frontend** (`frontend/`) — React UI only. Calls the API over HTTP/SSE.
2. **API layer** (`middleware/`) — FastAPI routes, JWT auth, request validation, HTTP errors.
3. **Backend / core** (`backend/`, import name `app`) — models, repositories, services, RAG pipeline, storage, cache. Installed with `pip install -e ./backend` and imported by FastAPI in the same process.

This keeps local setup simple while still showing clear boundaries for interviews and future scaling.

**Docs for submission:**

| Artifact | Link |
| -------- | ---- |
| System design (includes scalability) | [docs/system_design.md](docs/system_design.md) |
| Achieved vs future work | [docs/engineering-notes/achieved-and-future-work.md](docs/engineering-notes/achieved-and-future-work.md) |
| Known limitations | [docs/engineering-notes/known-limitations.md](docs/engineering-notes/known-limitations.md) |
| GitHub repo | [April-48/RAG-Application](https://github.com/April-48/RAG-Application) |

**More docs:**

- [System Design](docs/system_design.md)
- [API Design](docs/api_design.md)
- [Architecture Decision Records](docs/adr/)

## Quick Start

**Full guide:** [Setup Guide](docs/setup.md)

### Option A — Docker Compose (full stack)

```bash
chmod +x scripts/docker_setup.sh scripts/docker_start.sh
./scripts/docker_setup.sh          # first time: build, start, migrate
./scripts/docker_start.sh          # later restarts
```

Or manually:

```bash
cp .env.example .env          # set OPENAI_API_KEY for chat
docker compose up --build
docker compose run --rm middleware bash -lc "cd /app/backend && alembic upgrade head"
```

Open [http://localhost:5173](http://localhost:5173) · API docs [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B — Host dev (API on laptop, db/redis in Docker)

```bash
chmod +x scripts/dev_setup.sh scripts/dev_start.sh
./scripts/dev_setup.sh          # env, docker db+redis, deps, migrations
./scripts/dev_start.sh          # API on :8000
cd frontend && npm run dev      # second terminal → :5173
```

For Option B, use **localhost** in `DATABASE_URL` and `REDIS_URL` inside `.env`.

Set `OPENAI_API_KEY` (or `LLM_BASE_URL`) before testing chat.

**Health check:** `GET http://localhost:8000/health` → `{"status":"ok"}`

## Demo Flow

**Checklist:** [Demo Checklist](docs/engineering-notes/demo-checklist.md)

1. Sign up or log in.
2. Upload a **text-based** PDF, TXT, or DOCX (scanned PDFs need OCR — not built yet).
3. Wait until status is `ready`.
4. Open Chat and select the document.
5. Ask a question that the document can answer. Show streaming response and sources.
6. With Redis running, ask the **same question twice** to show cache hit (see checklist).
7. Optional: sign up a second user and confirm the first user's document id returns **404**.

## Engineering Docs

| Document | Purpose |
| -------- | ------- |
| [System Design](docs/system_design.md) | Architecture, scalability, RAG flows |
| [Achieved vs Future Work](docs/engineering-notes/achieved-and-future-work.md) | What works today vs what is left |
| [API Design](docs/api_design.md) | HTTP API surface |
| [Setup Guide](docs/setup.md) | Prerequisites, env vars, commands |
| [Demo Checklist](docs/engineering-notes/demo-checklist.md) | Pre-demo self-check |
| [Known Limitations](docs/engineering-notes/known-limitations.md) | MVP boundaries |
| [Troubleshooting](docs/engineering-notes/troubleshooting.md) | Common local fixes |
| [ADRs](docs/adr/) | Why I chose this stack and scope |

**Key ADRs:**

- [0001 — Three-layer architecture](docs/adr/0001-three-layer-architecture.md)
- [0002 — PostgreSQL + pgvector](docs/adr/0002-postgres-pgvector.md)
- [0003 — Single-document RAG scope](docs/adr/0003-single-document-rag-scope.md)
- [0004 — Background ingestion](docs/adr/0004-async-ingestion-backgroundtasks.md)
- [0005 — Redis answer cache](docs/adr/0005-redis-answer-cache.md)
- [0006 — Alembic migrations](docs/adr/0006-alembic-migrations.md)
- [0007 — Local storage vs S3](docs/adr/0007-local-storage-vs-s3.md)

Layer notes: [frontend](frontend/README.md) · [API layer](middleware/README.md) · [backend](backend/README.md)

## Testing

**Backend** — **48 pytest tests** (auth, document ownership, hybrid retrieval/query router, Redis cache keys, mocked chat):

```bash
cd backend
pip install -e .
pytest
```

**Frontend** — TypeScript check + production build (no Playwright/Cypress):

```bash
cd frontend
npm run build
```

Tests do **not** call real LLM or embedding APIs. The full upload → chat → sources flow is checked manually with the [demo checklist](docs/engineering-notes/demo-checklist.md).

## Known Limitations

This is an MVP, not a production RAG platform.

- One selected document per chat session
- Ingestion uses FastAPI `BackgroundTasks`, not a real job queue
- Local disk storage does not work well with multiple API servers
- Scanned/image-only PDFs need OCR (not implemented)
- Redis cache may serve stale answers until TTL after re-ingest
- Switching embedding dimensions requires a migration and re-ingest
- Redis chat rate limiting is optional and fail-open; not real abuse prevention

**Full list:** [Known Limitations](docs/engineering-notes/known-limitations.md)

## Future Improvements

See [System Design](docs/system_design.md) and [Achieved vs Future Work](docs/engineering-notes/achieved-and-future-work.md).
