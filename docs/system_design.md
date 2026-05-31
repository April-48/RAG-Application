# System Design

This document explains how my RAG app is built and how it could scale beyond a local MVP.

For a shorter “what works / what’s missing” list, see [achieved-and-future-work.md](engineering-notes/achieved-and-future-work.md).

## How this maps to the assignment

| Topic | Where to look |
| ----- | ------------- |
| RAG pipeline (upload → answer) | [README demo flow](../README.md#demo-flow) |
| Three-layer architecture | Layers below + [ADR 0001](adr/0001-three-layer-architecture.md) |
| Scaling beyond local | Section below + ADRs 0004–0007 |
| UI | React app in `frontend/` |

## Layers

```
┌────────────┐      HTTP/JSON      ┌──────────────┐      function calls      ┌───────────┐
│  frontend  │  ───────────────▶   │  middleware  │  ─────────────────────▶  │  backend  │
│ (React UI) │  ◀───────────────   │  (FastAPI)   │  ◀─────────────────────  │  (logic)  │
└────────────┘                     └──────────────┘                          └─────┬─────┘
                                                                                   │
                                                 ┌───────────────┬───────────┴───────────┐
                                                 │               │                       │
                                           ┌─────▼─────┐   ┌──────▼──────┐         ┌──────▼──────┐
                                           │  Postgres │   │ file storage│         │    Redis    │
                                           │ + pgvector│   │  uploads/   │         │cache/limit  │
                                           └───────────┘   └─────────────┘         └─────────────┘
                                                                                         │
                                                                                   ┌─────▼─────┐
                                                                                   │    LLM    │
                                                                                   └───────────┘
```

- **frontend/** — React UI only (upload, chat, sources). Calls the API over HTTP/SSE.
- **middleware/** — FastAPI routes, JWT, validation, HTTP errors.
- **backend/** (package `app`) — DB, RAG pipeline, storage, Redis, LLM. Installed with `pip install -e ./backend` and imported in the same process today.

## What runs locally

The MVP runs locally via Docker Compose (or host dev with db/redis in Docker). It has a React frontend, a FastAPI middleware layer, a Python backend package, Postgres with pgvector, optional Redis, and local file storage. Ingestion runs in the background after upload; the UI polls document status about every 5 seconds.

Default embeddings use local MiniLM at **384** dimensions. Switching to OpenAI (1536) needs a migration and re-ingest.

## Scalability (MVP → production)

Right now the whole app runs on one laptop with Docker Compose. That is enough for the homework demo, but the main parts are split so they can scale on their own later.

| Component | MVP today | How I would scale it |
| --------- | --------- | -------------------- |
| API traffic | One FastAPI process | Run several copies behind a load balancer. JWT auth is stateless, so any instance can handle a request. |
| Ingestion | `BackgroundTasks` in the API | Move to Redis + Celery/RQ workers. Upload would only enqueue a job; workers call the same `ingest_document()` function I already have. |
| Files | Local disk under `backend/storage/uploads/` | Swap `StorageBackend` to S3 (or similar). Routes and ingestion code would not need to change much. |
| Vector search | pgvector in Postgres | Add pgvector indexes first. If chunk count gets very large, consider a dedicated vector DB. |
| Frontend | Vite dev server | Build static files and host on a CDN. |

The same Redis service I use for cache and rate limiting could also act as the job queue broker later, so I would not need a totally new piece of infrastructure for workers.

### Target architecture (not built)

```
CDN (static frontend) → load balancer → FastAPI (×N)
                              ↓
              Postgres+pgvector   Redis   S3
                              ↓
                       Celery/RQ workers
```

More background: ADRs [0004](adr/0004-async-ingestion-backgroundtasks.md)–[0007](adr/0007-local-storage-vs-s3.md).

## Data model

- **User** — owns documents and chat sessions
- **Document** — `owner_id`, status (`uploaded` / `processing` / `ready` / `failed`), optional `display_name`
- **DocumentChunk** — text + embedding vector
- **ChatSession** — one per (user, document)
- **Message** — user/assistant text; assistant rows store `sources_json`
- **DocumentPermission** — table exists; not used in MVP

## Access control

Documents have an `owner_id`. Repositories only query by owner. Other users get **404** (not 403) so the API does not leak whether a document id exists. Retrieval and chat always filter by the selected `document_id`.

## Ingestion flow

1. Upload → save file → status `uploaded` → return immediately
2. Background task → `processing` → parse/chunk/embed → `ready` or `failed`
3. UI polls `GET /documents`

## Q&A flow

1. Check document is owned and `ready`
2. Optional Redis cache lookup
3. Hybrid retrieval (below)
4. LLM answer (or skip LLM for direct extraction / weak evidence)
5. Save history + sources; cache successful answers

## Hybrid RAG retrieval

Before the LLM, `query_router` picks a mode. This is simple rule-based routing plus pgvector — not BM25 fusion.

| Mode | Example question | LLM? |
| ---- | ---------------- | ---- |
| `document_beginning` | first sentence of the doc | Often no |
| `document_ending` | last paragraph | Often no |
| `page_lookup` | what is on page 3 | Usually yes |
| `section_lookup` | Methods section | Depends |
| `whole_document_summary` | summarize this document | Yes |
| `semantic` (default) | normal factual questions | Yes, if similarity ≥ 0.32 |

Sources shown in the UI come from **retrieved chunks**, not from parsing the LLM output.

## Redis

**Cache** (`ENABLE_REDIS_CACHE`): key `rag:answer:{user}:{doc}:{hash(question)}`, TTL 3600s default.

**Rate limit** (`ENABLE_RATE_LIMIT`): 10 asks/min per user on chat routes; HTTP 429 if exceeded.

Both are optional and fail-open.

## File storage

```
backend/storage/uploads/{user_id}/{document_id}/<file>
```

Uses `StorageBackend` so S3 can replace local disk later.

## MVP limits (honest)

- Single document per chat
- BackgroundTasks, not a real queue
- Local disk only
- No OCR for scanned PDFs
- Rule-based query router
- Owner-only access

More detail: [known-limitations.md](engineering-notes/known-limitations.md).

## Future (scalability focus)

The most important next steps are reliability and scalability, not new features.

**Ingestion workers.** Upload already returns immediately and only schedules `ingest_document()`. That boundary is ready for a queue: on upload I would push a job to Redis, and separate worker processes would run the same ingestion code. Jobs would survive API restarts instead of dying with BackgroundTasks. The frontend could keep polling `documents.status` the same way.

**Object storage.** Files today live on local disk, which is fine for one container but not for multiple API servers. I already read and write through `StorageBackend`, so moving to S3 would mostly mean implementing a new backend class, not rewriting upload or chat routes.

**Horizontal API scaling.** The FastAPI layer does not store session state in memory — it uses JWT plus Postgres/Redis. That means I can run more API containers behind a load balancer without changing the RAG logic inside `app`.

**Vector search at scale.** pgvector inside Postgres is enough for my demo documents. If users uploaded much larger corpora, I would add pgvector indexes (IVFFlat/HNSW) or, at very large scale, move vectors to a dedicated store while keeping document metadata in Postgres.

**Cloud deploy (e.g. Supabase).** I did not deploy this MVP to the cloud, but the stack maps cleanly to managed services. Postgres + pgvector could move to **Supabase** (or RDS) — I would point `DATABASE_URL` at the hosted instance and run `alembic upgrade head`; the ORM and pgvector queries stay the same. Uploads would leave local disk for **Supabase Storage** or **S3** via a new `StorageBackend` class. Redis cache and rate limits could use **Upstash Redis** or any managed Redis. The FastAPI app could run on **Railway**, **Render**, or **Fly.io** as one or more containers behind their load balancer, with the React frontend on a static host or CDN. I would **not** switch to MongoDB — users, chunks, vectors, and chat history all live in Postgres today; moving to MongoDB would mean rewriting repositories and retrieval, not a config change.

Things like multi-document chat, OCR, or shared folders are useful product ideas, but they are separate from this core scaling path.

## Related docs

- [achieved-and-future-work.md](engineering-notes/achieved-and-future-work.md)
- [setup.md](setup.md) · [api_design.md](api_design.md) · [adr/](adr/)
