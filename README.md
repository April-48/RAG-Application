# RAG Document Q&A App

A full-stack RAG application where users upload PDF/TXT/DOCX files, ask questions about a **selected document**, and receive answers grounded in retrieved chunks—with cited sources. This is a **coursework MVP** (Docker Compose on a laptop) with clear frontend/API/backend separation and documented scalability paths — not a production deployment.

> The local version is a Docker Compose MVP, but the architecture separates frontend, API, backend logic, database, cache, and storage. That makes it possible to scale the API horizontally, move ingestion to workers, replace local storage with S3, and upgrade vector search as data grows.

## Features

- User signup/login with JWT-based authentication
- Upload PDF, TXT, and DOCX documents
- Background document ingestion with status tracking (`uploaded` → `processing` → `ready` / `failed`)
- Text chunking, embeddings, and vector search with PostgreSQL + pgvector
- Single-document chat sessions with grounded source snippets
- Streaming chat responses via SSE
- Optional Redis answer cache for repeated questions (fail-open if Redis is down)
- Optional Redis chat rate limiting on LLM ask endpoints (10/min per user, fail-open)
- Owner-scoped document access — users cannot read each other's files
- Rename documents, search lists, open original uploads, deep link chat via `?doc=`

## Tech Stack

| Area | Technology |
| ---- | ---------- |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| API layer | FastAPI, Pydantic, JWT |
| Application/core layer | Python services, repositories, RAG pipeline (`app` package) |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis (optional answer cache + chat rate limit) |
| Migrations | Alembic |
| Storage | Local disk (MVP); S3-compatible backend planned |
| LLM / embeddings | OpenAI-compatible chat; local MiniLM or OpenAI embeddings via env config |

## Architecture Overview

Layered layout in one repo — **logical separation**, not three deployed services in the MVP:

1. **Frontend** — React UI only; calls the API over HTTP/SSE.
2. **API layer** — FastAPI routes, JWT auth, request validation, HTTP error mapping (`middleware/app/` in the repo).
3. **Application/core layer** — models, repositories, services, storage, cache, RAG pipeline. Installed editable (`pip install -e ./backend`) and imported **in-process** by FastAPI.

This keeps local setup simple while preserving clear boundaries for workers or service extraction later — which is what the grading rubric asks for on system design.

**Submission artifacts (docs):**

| Artifact | Link |
| -------- | ---- |
| System design (incl. scalability) | [docs/system_design.md](docs/system_design.md) |
| Achieved vs future work | [docs/engineering-notes/achieved-and-future-work.md](docs/engineering-notes/achieved-and-future-work.md) |
| Known limitations | [docs/engineering-notes/known-limitations.md](docs/engineering-notes/known-limitations.md) |
| GitHub repo | [April-48/RAG-Application](https://github.com/April-48/RAG-Application) |

**Full design:**

- [System Design](docs/system_design.md)
- [API Design](docs/api_design.md)
- [Architecture Decision Records](docs/adr/)

## Quick Start

**Full guide:** [Setup Guide](docs/setup.md)

### Option A — Docker Compose (full stack)

```bash
chmod +x scripts/docker_setup.sh scripts/docker_start.sh
./scripts/docker_setup.sh          # build, start, migrate (first time)
./scripts/docker_start.sh          # later restarts
```

Or manually:

```bash
cp .env.example .env          # set OPENAI_API_KEY for chat
docker compose up --build
docker compose run --rm middleware bash -lc "cd /app/backend && alembic upgrade head"
```

Open [http://localhost:5173](http://localhost:5173) · API docs [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B — Host dev (scripts + db/redis in Docker)

```bash
chmod +x scripts/dev_setup.sh scripts/dev_start.sh
./scripts/dev_setup.sh          # env, docker db+redis, deps, migrations
./scripts/dev_start.sh          # API on :8000
cd frontend && npm run dev      # second terminal → :5173
```

Use **localhost** `DATABASE_URL` / `REDIS_URL` in `.env` for Option B.

Set `OPENAI_API_KEY` (or `LLM_BASE_URL`) before testing chat.

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
| [System Design](docs/system_design.md) | Architecture, scalability, RAG flows |
| [Achieved vs Future Work](docs/engineering-notes/achieved-and-future-work.md) | What ships vs production next steps |
| [API Design](docs/api_design.md) | HTTP API surface |
| [Setup Guide](docs/setup.md) | Prerequisites, env vars, commands |
| [Demo Checklist](docs/engineering-notes/demo-checklist.md) | Pre-demo self-check |
| [Known Limitations](docs/engineering-notes/known-limitations.md) | MVP boundaries |
| [Troubleshooting](docs/engineering-notes/troubleshooting.md) | Common local fixes |
| [ADRs](docs/adr/) | Why I chose this stack and scope |

**Key ADRs:**

- [0001 — Layered frontend / API / application architecture](docs/adr/0001-three-layer-architecture.md)
- [0002 — PostgreSQL + pgvector](docs/adr/0002-postgres-pgvector.md)
- [0003 — Single-document RAG scope](docs/adr/0003-single-document-rag-scope.md)
- [0004 — Background ingestion (BackgroundTasks)](docs/adr/0004-async-ingestion-backgroundtasks.md)
- [0005 — Redis answer cache](docs/adr/0005-redis-answer-cache.md)
- [0006 — Alembic migrations](docs/adr/0006-alembic-migrations.md)
- [0007 — Local storage vs S3](docs/adr/0007-local-storage-vs-s3.md)

Layer notes: [frontend](frontend/README.md) · [API layer](middleware/README.md) · [application core](backend/README.md)

## Testing

**Backend** (pytest — auth, document ownership, RAG helpers, Redis cache keys, mocked chat):

```bash
cd backend
pip install -e .
pytest
```

**Frontend** validation uses TypeScript check + production build (no Playwright/Cypress):

```bash
cd frontend
npm run build
```

Automated tests focus on core security and RAG assumptions. Real LLM or embedding APIs are **not** called in tests. End-to-end demo flow is validated manually with [`docs/engineering-notes/demo-checklist.md`](docs/engineering-notes/demo-checklist.md).

## Known Limitations

This is an MVP, not a production RAG platform.

- One selected document per chat session
- Ingestion uses FastAPI `BackgroundTasks`, not a durable worker queue
- Local disk storage is not multi-instance safe
- Scanned/image-only PDFs need OCR (not implemented)
- Redis cache may serve stale answers until TTL after re-ingest
- Switching embedding dimensions requires migration and re-ingestion
- Redis chat rate limiting is optional and fail-open (`ENABLE_RATE_LIMIT`); not production-grade abuse prevention

**Full list:** [Known Limitations](docs/engineering-notes/known-limitations.md)

## Future Improvements

See [System Design](docs/system_design.md) and [Achieved vs Future Work](docs/engineering-notes/achieved-and-future-work.md).
