# System Design

Design of the RAG Document Q&A application. It describes the **current local MVP**
architecture (what is implemented) and a **production scalable** target (future
work). Implementation details that already exist are called out as such.

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

- **frontend** — pure UI. Talks only to the middleware over HTTP.
- **middleware** — thin FastAPI layer: routing, JWT auth, validation, permission
  checks, mapping domain exceptions to HTTP responses. Delegates all work to the
  backend.
- **backend** — all business logic: models, repositories, services, RAG pipeline,
  storage, embeddings, retrieval, Redis cache, and LLM calls. Packaged as an
  installable internal package (top-level `app`) via `backend/pyproject.toml` and
  installed editable (`pip install -e ./backend`), so the middleware imports it as
  `app.*` with no `sys.path` manipulation. It runs in-process, not as a separate
  HTTP service.

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

## Production scalable architecture (future)

How it would scale beyond a single box (not implemented now):

- **Frontend** hosted on Vercel or S3 + CloudFront (static build + CDN).
- **FastAPI API servers** behind a load balancer (stateless, horizontally scaled).
- **Backend services** can be split out (e.g. an ingestion service) if needed.
- **Managed Postgres** with pgvector; vector indexes (IVFFlat/HNSW) or a dedicated
  vector DB (**Qdrant, Pinecone, Weaviate, Milvus**) for larger corpora.
- **S3 / private object storage** for uploaded files (behind the existing
  `StorageBackend` interface).
- **Redis** for both cache **and** a queue/broker.
- **Celery / RQ workers** consuming a Redis queue for durable, distributed,
  retryable document ingestion.
- **Rate limiting**, **monitoring/logging**, and **audit logs** for document access.
- **Optional shared-document permissions** (the `document_permissions` table is
  already in the schema).

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
- No rate limiting, monitoring, or audit logs yet.

## Future work

- Redis + Celery/RQ workers for ingestion; S3 for uploads.
- Dedicated vector DB or pgvector indexes at scale.
- Shared-document permissions, rate limiting, monitoring/logging, audit logs.
- Deep-linkable `/chat/:documentId` routes.
- More document types (PPTX/HTML/Markdown) and OCR for scanned PDFs — PDF, TXT,
  and DOCX are supported today.

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
