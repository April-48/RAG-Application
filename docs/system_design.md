# System Design

This document explains how the RAG Document Q&A app is structured today and how it can scale beyond a local MVP.

It covers:

1. What runs today with Docker Compose
2. How the frontend, middleware, and backend layers are separated
3. How the system could evolve into a more distributed production architecture

For a shorter “achieved vs future” checklist, see
[`engineering-notes/achieved-and-future-work.md`](engineering-notes/achieved-and-future-work.md).

## How this maps to grading criteria

| Grading area | Where to look in this project |
| ------------ | ----------------------------- |
| **App quality** | Working signup/login, upload, status polling, single-doc chat, sources, file download, chat history — demo flow in [README](../README.md#demo-flow) |
| **System design / front–back separation** | Three layers below + [ADR 0001](adr/0001-three-layer-architecture.md) |
| **Scalability beyond local / distributed architecture** | **Scalability beyond local development** section below + ADRs 0004–0007 |
| **Clean UI/UX** | React + Tailwind; status badges, streaming chat, source panel — see frontend |

Artifacts for submission: this file, [achieved/future work](engineering-notes/achieved-and-future-work.md), [known limitations](engineering-notes/known-limitations.md), and the [GitHub repo](https://github.com/April-48/RAG-Application).

## Layers

```
┌────────────┐      HTTP/JSON      ┌──────────────┐      function calls      ┌───────────┐
│  frontend  │  ───────────────▶   │  middleware  │  ─────────────────────▶  │  backend  │
│ (React UI) │  ◀───────────────   │  (FastAPI)   │  ◀─────────────────────  │  (logic)  │
└────────────┘                     └──────────────┘                          └─────┬─────┘
                                                                                   │
                                                       ┌───────────────┬───────────┴───────┬───────────────┐
                                                       │               │                   │               │
                                                 ┌─────▼─────┐   ┌──────▼──────┐     ┌──────▼──────┐  ┌─────▼─────┐
                                                 │  Postgres │   │ file storage│     │    Redis    │  │    LLM    │
                                                 │ + pgvector│   │  uploads/   │     │answer cache │  │ provider  │
                                                 └───────────┘   └─────────────┘     └─────────────┘  └───────────┘
```

- **frontend/** (`frontend/`) — React UI only. Pages, forms, polling, SSE chat.
  Talks to the API over HTTP; no business logic.
- **middleware/** (`middleware/`) — FastAPI **API layer**: routes, JWT auth,
  request validation, permission checks, mapping domain errors to HTTP status
  codes. Delegates all work to the core package.
- **backend/** (`backend/`, import name `app`) — **application/core layer**:
  models, repositories, services, RAG pipeline, storage, embeddings, retrieval,
  Redis cache, LLM calls. Installed editable (`pip install -e ./backend`) and
  imported as `app.*` in-process today — not a separate HTTP service in the MVP,
  but the package boundary is the same one I would extract for workers or
  microservices later.

## Current local MVP architecture

What runs today, on a single machine:

- **React frontend** (Vite/TS/Tailwind) — auth, upload, document list with status
  polling, chat with SSE streaming and a SourcePanel.
- **FastAPI middleware** — routes, JWT auth, validation, permissions.
- **Backend business/RAG package** — `rag/pipeline.py` orchestrates
  loader → text_splitter → embedding_service → retrieval_service →
  prompt_builder → llm_service, plus repositories/services.
- **Postgres + pgvector** — users, documents, chunks (+384-dim embeddings by
  default with the local model; 1536 if switched to OpenAI), chat sessions,
  messages, permissions.
- **Alembic migrations** — schema management (`backend/alembic`).
- **Redis answer cache** — optional, for repeated RAG answers.
- **Redis chat rate limit** — optional cap on `POST /chat/.../ask` and `/ask/stream`
  (default 10 requests/minute per user via `INCR` + `EXPIRE`; HTTP 429 when exceeded;
  fail-open if Redis is disabled or unreachable).
- **Local file storage** — uploads under `backend/storage/uploads/{user}/{doc}/`.
- **Async ingestion:** **Current:** FastAPI `BackgroundTasks` (in-process, MVP).
  **Production:** Redis + Celery or RQ workers for durable, distributed ingestion.
- **Frontend polling** — `GET /documents` every 5s while any doc is in progress.
- **Swappable model layer** — `EMBEDDING_PROVIDER` / `LLM_PROVIDER` select the
  implementation via the `get_embedding_service()` / `get_llm_service()`
  factories. Embeddings: local sentence-transformers `all-MiniLM-L6-v2`
  (default, 384-dim, free/offline) or OpenAI `text-embedding-3-small`
  (1536-dim). LLM: `rag/llm_service.py` wraps an OpenAI-compatible client, so
  OpenAI / OpenRouter / a local Ollama-compatible endpoint can be used by
  swapping credentials, model, and `LLM_BASE_URL`. The rest of the pipeline
  depends only on the `Embedder` / `LLM` interfaces.
  - **Switching embedding provider** changes the vector dimension (384 ↔ 1536).
    That requires updating the `document_chunks.embedding` `Vector(...)` column
    via a migration **and** re-ingesting existing documents — vectors of
    different dimensions are not interchangeable and cannot be compared.

## Scalability beyond local development

The project runs locally with Docker Compose, but each major responsibility is
separated so it can scale on its own. Each row ties a real concern to **what the
code does today** and **what I would change in production**.

| Scalability concern | Current implementation (evidence in repo) | Production scaling plan |
| ------------------- | ----------------------------------------- | ----------------------- |
| More API traffic | FastAPI middleware in its own Docker service; JWT auth (no server-side session store) | Multiple API instances behind a load balancer |
| Slow / blocking uploads | Upload returns immediately; ingestion via `BackgroundTasks` + `ingest_document()` | Redis queue + Celery/RQ workers; API only enqueues jobs |
| Large or many files | Files under `backend/storage/uploads/`; `StorageBackend` interface | S3 / private object storage shared across API and worker nodes |
| Growing vector data | Postgres + pgvector; retrieval filtered by `document_id` + owner | pgvector indexes (IVFFlat/HNSW) or dedicated vector DB (Qdrant, Pinecone, Weaviate, Milvus) |
| Expensive repeated LLM calls | Redis answer cache + per-user chat rate limit on ask endpoints, fail-open | Redis cluster, TTL tuning, broader rate limiting |
| Schema changes at scale | Alembic migrations in `backend/alembic/` | Run migrations in CI/CD before deploy |
| Multi-user isolation | `owner_id` on documents; owner-scoped repository queries | RBAC, workspaces, audit logs; optional `document_permissions` |
| Frontend delivery | Vite dev server in Docker (demo) | `npm run build` → static assets on CDN |
| Database size | Single Postgres container with named volume | Managed Postgres, read replicas if needed, connection pooling |

How each layer scales:

- The **React frontend** can be built as static files and served through a CDN.
- The **FastAPI API layer** is mostly stateless (JWT + Postgres/Redis for state),
  so multiple instances can sit behind a load balancer.
- **Document ingestion** is already off the upload request path. Production =
  swap `BackgroundTasks` for Redis + Celery/RQ workers using the same
  `ingest_document(document_id, owner_id)` entrypoint.
- **Uploaded files** use local storage in the MVP, but callers go through
  `StorageBackend` — S3 is a backend swap, not a rewrite.
- **Postgres + pgvector** handles relational data and vector search today; at
  larger scale, add indexes or a dedicated vector database.
- **Redis** is used as an answer cache now; the same Redis can later back queues,
  rate limits, and job status.
- Every document is scoped by `owner_id`, and retrieval is filtered by authorized
  `document_id` to avoid cross-user leakage.

### Production target architecture (not deployed)

```
                    ┌─────────────┐
                    │ CDN / static│  ←  frontend build
                    │   frontend  │
                    └──────┬──────┘
                           │ HTTPS
                    ┌──────▼──────┐
                    │Load balancer│
                    └──────┬──────┘
              ┌────────────┼────────────┐
        ┌─────▼─────┐            ┌─────▼─────┐
        │ FastAPI   │            │ FastAPI   │  ←  stateless API replicas
        │ instance  │            │ instance  │
        └─────┬─────┘            └─────┬─────┘
              │                        │
              └────────────┬───────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
┌────▼────┐          ┌─────▼─────┐         ┌─────▼─────┐
│ Postgres│          │   Redis   │         │ S3 / obj  │
│+pgvector│          │cache+queue│         │  storage  │
└─────────┘          └─────┬─────┘         └───────────┘
                           │
                     ┌─────▼─────┐
                     │  Celery/  │  ←  ingestion workers
                     │ RQ workers│
                     └───────────┘
```

See ADRs [0004](adr/0004-async-ingestion-backgroundtasks.md),
[0005](adr/0005-redis-answer-cache.md), [0006](adr/0006-alembic-migrations.md),
[0007](adr/0007-local-storage-vs-s3.md) for why these MVP choices were made.

## Data model

- **User** — has many documents, chat sessions, permissions.
- **Document** — belongs to a user via `owner_id`; has a lifecycle `status`
  (`uploaded`/`processing`/`ready`/`failed`); has many chunks. `filename` is the
  original uploaded name; optional `display_name` is a user-editable UI label
  (`PATCH /documents/{id}` does not rename the file on disk).
- **DocumentChunk** — belongs to a document; stores `chunk_text` and a pgvector
  `embedding` (384-dim for the default local `all-MiniLM-L6-v2`; 1536 for OpenAI
  `text-embedding-3-small`).
- **ChatSession** — per (user, document) conversation; has many messages.
- **Message** — `role`/`content`; assistant messages carry `sources_json`.
- **DocumentPermission** — future shared access (schema only).

## User document isolation (access control)

1. Every document carries an `owner_id`.
2. Repositories expose **only** owner-scoped queries, so isolation is enforced at
   the data layer, not just in routes.
3. The middleware authenticates via JWT; services re-check access and raise
   `DocumentNotFoundError` for both missing and unauthorized documents (never
   leaking existence).
4. Retrieval, chat, and history are always filtered by `document_id` **and** the
   authorized user.
5. **Original file download** — `GET /documents/{id}/file` returns the uploaded
   file via `FileResponse` after the same ownership/permission checks used for
   chat. Internal `storage_path` is never sent to clients. PDF/TXT are opened in
   a new browser tab; DOCX is downloaded.

## RAG upload pipeline (ingestion flow)

1. User uploads a file; middleware validates auth + type and calls
   `document_service.upload`.
2. The file is saved by the storage backend under
   `backend/storage/uploads/{user_id}/{document_id}/`, and a `Document` row is
   created with status `uploaded`. **Upload returns immediately.**
3. Ingestion runs off the request path. **Current:** FastAPI `BackgroundTasks`
   invoke `workers/ingestion_worker.ingest_document` (in its own DB session, not a
   distributed worker). **Production:** enqueue the same job to Redis + Celery or
   RQ workers. The service sets status → `processing`, then delegates the
   mechanics to `RAGPipeline.ingest`:
   - `loader` routes by extension and extracts text (PyMuPDF for PDF; plain read
     for TXT; python-docx — paragraphs + basic tables — for DOCX).
   - `text_splitter` chunks the text (1000 chars, 200 overlap).
   - `embedding_service` embeds chunks (default local sentence-transformers
     `all-MiniLM-L6-v2`, 384-dim; or OpenAI `text-embedding-3-small`, 1536-dim).
   - chunks + embeddings persisted via `chunk_repository`.
   - status → `ready` (or `failed` on any error / empty extraction).
4. The frontend polls `GET /documents` and observes the status transitions.

### Future: Redis-backed async ingestion (Celery/RQ)

**Current:** FastAPI `BackgroundTasks` (in-process, MVP).

**Production:** Redis + Celery or RQ workers (or Arq) backed by a Redis queue.

`BackgroundTasks` runs in the API process — fine for an MVP, but not durable or
horizontally scalable. Target evolution:

- Use a task queue (**Celery** or **RQ**) with **Redis as the broker**.
- On upload, enqueue an ingestion job (`document_id` + `owner_id`) instead of a
  `BackgroundTask`.
- Dedicated **worker** processes run `ingest_document`, scaling independently of
  the API and surviving restarts/retries.
- Job state surfaces through the existing `documents.status` column, so the
  frontend poller is unchanged.

Celery is intentionally **not** implemented now — the
`ingest_document(document_id, owner_id)` boundary is already queue-friendly, so
the swap is localized to the upload route and a worker entrypoint.

## RAG question-answering pipeline (retrieval flow)

1. User asks a question about a document.
2. Middleware verifies the document belongs to the authenticated user.
3. **Cache check** — `chat_service` looks up Redis with key
   `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`. On a hit,
   the cached answer + sources are returned immediately (no retrieval, no LLM).
4. On a miss, the question is embedded and a pgvector cosine-distance search runs,
   **filtered by `document_id`** (top-k = 5).
5. `prompt_builder` builds a context-only prompt; `llm_service` calls the LLM
   (one-shot `generate` or `generate_stream` for SSE).
6. The answer + citations are persisted (chat history) and, on success, written to
   the Redis cache, then returned. Streaming and cache-hit responses use the same
   SSE event shape (`token` → `sources` → `done`).

## Redis cache flow

- **Key**: `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`,
  where `normalized_question = question.strip().lower()` (normalized for the key
  only; the stored/queried question is unchanged).
- **Value**: JSON `{"answer": str, "sources": [{chunk_index, page_number, chunk_text}, ...]}`.
- **TTL**: `CACHE_TTL_SECONDS` (default 3600s).
- **Optional & fail-safe**: governed by `ENABLE_REDIS_CACHE`. Every Redis call is
  wrapped; a disabled/unreachable Redis degrades to a miss/no-op, and the request
  falls back to the full RAG flow. Cache behavior is logged (`app.cache.*`).
- **Not cached**: errors (e.g. LLM unavailable) and "insufficient context"
  non-answers.
- **Isolation**: keys are namespaced per user and per document.

## Redis chat rate limiting

Protects LLM cost and abuse on chat ask endpoints only (`POST /chat/{document_id}/ask`
and `/ask/stream`). History, upload, and auth are not rate limited.

- **Key:** `rate:user:{user_id}:chat:{yyyyMMddHHmm}` (UTC minute bucket)
- **Algorithm:** `INCR` + `EXPIRE 60` on first hit in the bucket
- **Default cap:** `CHAT_RATE_LIMIT_PER_MINUTE=10` when `ENABLE_RATE_LIMIT=true`
- **On exceed:** HTTP `429` with
  `Too many requests. Please wait a moment and try again.` and optional
  `Retry-After` (seconds until the next minute)
- **Fail-open:** if Redis is disabled or errors, the request proceeds (same pattern
  as the answer cache)

## File storage layout

```
backend/storage/uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

Storage backends implement a common interface (`storage/base.py`) — local disk
now, S3/object storage later, with no caller changes.

## Current limitations

- Supported file types: PDF (`.pdf`), TXT (`.txt`), DOCX (`.docx`).
- No OCR — scanned/image-only PDFs are not supported.
- Legacy `.doc` is not supported; DOCX covers text paragraphs and basic tables
  only (complex formatting/images are not interpreted).
- In-process `BackgroundTasks` ingestion (not durable / not distributed).
- Local file storage only.
- Single chat session per (user, document).
- Owner-only access (sharing table exists but is unused).
- Redis-based chat rate limiting is implemented as an optional, fail-open MVP feature (enable via `ENABLE_RATE_LIMIT`); not production-grade abuse prevention yet.
- No monitoring or audit logs yet.

## Future work (product scope)

Scaling paths are covered in the **Scalability beyond local development** section above. Remaining product gaps:

- Shared-document permissions (schema exists; routes/UI not wired)
- Multi-document retrieval and chat sessions
- OCR for scanned/image-only PDFs
- More document types (PPTX/HTML/Markdown)
- Cache invalidation on re-ingest
- Production-grade rate limiting, monitoring/logging, audit logs

### Multi-document Q&A (deferred)

**Current MVP:** Single-document RAG Q&A. Each chat session is scoped to one
user and one document.

**Future work:** Multi-document Q&A can be added by introducing document-set
scoped retrieval, document-set cache keys, and multi-document chat sessions.

Concretely, this would change:

- **Retrieval scope** — search across a set of documents (still owner-scoped)
  rather than one `document_id`.
- **Cache key** — replace the single `document_id` in
  `rag:answer:{user_id}:{document_id}:{hash}` with a stable fingerprint of the
  document set so cached answers don't mismatch.
- **Chat session model** — associate a `ChatSession` with a document set (or
  record the source document per message) instead of one optional `document_id`.
- **UI** — a single/multi document toggle to choose what to query.

Per the current scope, the retrieval scope, chat session model, Redis cache key
structure, and chat routing are **not** modified for multi-document support.

## Related docs

- [`achieved-and-future-work.md`](engineering-notes/achieved-and-future-work.md) — what the app does today vs remaining product gaps.
- [`setup.md`](setup.md) — local install, env vars, commands.
- [`api_design.md`](api_design.md) — HTTP API surface exposed by the middleware.
- [`adr/`](adr/) — Architecture Decision Records (why we chose this stack and scope).
- [`engineering-notes/`](engineering-notes/) — Troubleshooting, known limitations, demo checklist.

### Architecture decisions (ADRs)

| ADR | Topic |
| --- | ----- |
| [0001](adr/0001-three-layer-architecture.md) | Layered frontend / API / application architecture |
| [0002](adr/0002-postgres-pgvector.md) | PostgreSQL + pgvector |
| [0003](adr/0003-single-document-rag-scope.md) | Single-document RAG MVP scope |
| [0004](adr/0004-async-ingestion-backgroundtasks.md) | Background ingestion with BackgroundTasks |
| [0005](adr/0005-redis-answer-cache.md) | Optional Redis answer cache |
| [0006](adr/0006-alembic-migrations.md) | Alembic schema migrations |
| [0007](adr/0007-local-storage-vs-s3.md) | Local storage now, S3 later |
