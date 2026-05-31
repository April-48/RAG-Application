# System Design

This document explains how the RAG Document Q&A app is built today, and how it could grow beyond a local MVP.

It covers:

1. What runs with Docker Compose today
2. How the frontend, API, and backend layers are separated
3. How the system could scale later

For a shorter checklist of what works vs what is missing, see [achieved-and-future-work.md](engineering-notes/achieved-and-future-work.md).

## How this maps to grading

| Area | Where to look |
| ---- | ------------- |
| **App quality** | Signup/login, upload, status polling, chat, sources, file download — [README demo flow](../README.md#demo-flow) |
| **System design / separation** | Three layers below + [ADR 0001](adr/0001-three-layer-architecture.md) |
| **Scalability** | Scalability section below + ADRs 0004–0007 |
| **UI/UX** | React + Tailwind; streaming chat, source panel — see `frontend/` |

Submission docs: this file, [achieved/future work](engineering-notes/achieved-and-future-work.md), [known limitations](engineering-notes/known-limitations.md), and the [GitHub repo](https://github.com/April-48/RAG-Application).

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

- **frontend/** — React UI only. Pages, forms, polling, SSE chat. No business logic.
- **middleware/** — FastAPI **API layer**: routes, JWT, validation, HTTP errors. Calls the backend package.
- **backend/** (import name `app`) — **core layer**: models, repos, services, RAG pipeline, storage, cache, LLM. Installed with `pip install -e ./backend` and imported in the same process as FastAPI today.

## What runs locally today

On one machine (Docker Compose or host dev):

- **React frontend** — auth, upload, document list with status polling, chat with SSE and a source panel
- **FastAPI middleware** — routes, JWT, validation
- **Backend `app` package** — `rag/pipeline.py` runs loader → split → embed → retrieve → prompt → LLM
- **Postgres + pgvector** — users, documents, chunks (384-dim vectors by default), chat tables
- **Alembic** — schema migrations in `backend/alembic`
- **Redis answer cache** — optional; speeds up repeat questions
- **Redis chat rate limit** — optional; caps ask routes (default 10/min per user)
- **Local file storage** — `backend/storage/uploads/{user_id}/{document_id}/`
- **Background ingestion** — FastAPI `BackgroundTasks` today; Celery/RQ workers later
- **Frontend polling** — `GET /documents` every ~5s while any doc is in progress
- **Swappable models** — `EMBEDDING_PROVIDER` and `LLM_BASE_URL` pick the implementation via factory functions

**Embedding note:** default local model is `all-MiniLM-L6-v2` at **384** dimensions. OpenAI `text-embedding-3-small` uses **1536**. Switching requires a migration and re-ingesting all documents.

## Scalability beyond local development

The app runs on Docker Compose today, but each part is separated so it can scale later.

| Concern | What we have now | What I would do in production |
| ------- | ---------------- | ----------------------------- |
| More API traffic | One FastAPI container; JWT auth | Multiple API instances behind a load balancer |
| Slow uploads | Upload returns fast; ingest in BackgroundTasks | Redis queue + Celery/RQ workers |
| Many/large files | Local disk + `StorageBackend` interface | S3 or similar object storage |
| More vector data | Postgres + pgvector, filtered by document | pgvector indexes or a dedicated vector DB |
| Repeat LLM calls | Redis answer cache + rate limit | Redis cluster, better rate limiting |
| Schema changes | Alembic migrations | Run migrations in CI before deploy |
| User isolation | `owner_id` on documents | RBAC, workspaces, audit logs |
| Frontend | Vite dev server in Docker | Static build on a CDN |
| Database size | One Postgres container | Managed Postgres, read replicas, pooling |

How each layer could scale:

- **Frontend** — build static files and serve from a CDN
- **API** — mostly stateless (JWT + Postgres/Redis), so you can run multiple copies
- **Ingestion** — already off the upload path; swap BackgroundTasks for workers using the same `ingest_document()` function
- **Files** — go through `StorageBackend`; S3 is a backend swap, not a full rewrite
- **Vectors** — pgvector works for MVP; add indexes or a vector DB at larger scale
- **Redis** — cache today; same Redis can back queues and job status later
- **Security** — every document has `owner_id`; retrieval always filters by authorized `document_id`

### Production target (not deployed)

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
        │ FastAPI   │            │ FastAPI   │
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
                     │  Celery/  │
                     │ RQ workers│
                     └───────────┘
```

See ADRs [0004](adr/0004-async-ingestion-backgroundtasks.md), [0005](adr/0005-redis-answer-cache.md), [0006](adr/0006-alembic-migrations.md), [0007](adr/0007-local-storage-vs-s3.md).

## Data model

- **User** — owns documents, chat sessions, permissions (future)
- **Document** — has `owner_id`, status (`uploaded` / `processing` / `ready` / `failed`), chunks. `filename` is the original name; `display_name` is an optional UI label (`PATCH` does not rename the file on disk)
- **DocumentChunk** — chunk text + pgvector `embedding` (384 default; 1536 for OpenAI)
- **ChatSession** — one per (user, document)
- **Message** — role, content; assistant messages store `sources_json`
- **DocumentPermission** — future sharing (schema only in MVP)

## User document isolation

1. Every document has an `owner_id`.
2. Repositories only expose owner-scoped queries.
3. Middleware checks JWT; services raise `DocumentNotFoundError` for missing or unauthorized docs (always `404`).
4. Retrieval, chat, and history filter by `document_id` and the logged-in user.
5. **File download** — `GET /documents/{id}/file` returns the file after the same checks. Clients never see `storage_path`.

## RAG upload pipeline (ingestion)

1. User uploads a file. Middleware checks auth and file type, then calls `document_service.upload`.
2. File is saved under `backend/storage/uploads/{user_id}/{document_id}/`. A row is created with status `uploaded`. **Upload returns immediately.**
3. A background task runs `ingestion_worker.ingest_document`:
   - status → `processing`
   - `RAGPipeline.ingest`: extract text (PDF/TXT/DOCX) → split (1000 chars, 200 overlap) → embed → save chunks
   - status → `ready` or `failed`
4. Frontend polls `GET /documents` and watches status change.

**Later:** replace BackgroundTasks with Redis + Celery/RQ workers. The frontend poller can stay the same because status still lives on the `documents` row.

## RAG question-answering pipeline

1. User asks a question about a document.
2. Middleware checks ownership and that status is `ready`.
3. **Cache check** — Redis key `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`. On hit, return cached answer + sources (no retrieval, no LLM).
4. On miss, **hybrid retrieval** runs (see next section).
5. **Generation** — if retrieval returns `direct_answer` or `skip_llm_message`, skip the LLM. Otherwise build a prompt and call the LLM (JSON or SSE stream).
6. Save answer + sources to chat history. On success, write to Redis cache. SSE shape: `token` → `sources` → `done`.

## Hybrid RAG retrieval

Before calling the LLM, `query_router.route_question()` picks a **QueryMode**. `RetrievalService.retrieve()` runs the matching strategy.

This is **not** BM25 + vector fusion. It is simple phrase rules plus metadata lookup, with pgvector for the default semantic path.

| QueryMode | Example questions | What it does | LLM |
| --------- | ----------------- | ------------ | --- |
| `DOCUMENT_BEGINNING` | “first sentence of the document” | First chunk; extract text directly | Skipped when possible |
| `DOCUMENT_ENDING` | “last paragraph”, “how does it end” | Last chunk; extract text directly | Skipped when possible |
| `PAGE_LOOKUP` | “what is on page 3?” | Chunks with matching `page_number` | Used unless page not found |
| `SECTION_LOOKUP` | “first sentence of Methods section” | Match section heading in chunks | Often skipped for first sentence |
| `WHOLE_DOCUMENT_SUMMARY` | “summarize this document” | Pick up to 6 representative chunks | Used — LLM summarizes |
| `SEMANTIC` (default) | general questions | pgvector search, top-k = `RETRIEVAL_TOP_K` (default 5) | Used if evidence is strong enough |

### Similarity threshold (SEMANTIC mode)

Semantic search uses cosine similarity (`1 - cosine_distance`). If the best score is below **`RETRIEVAL_MIN_SIMILARITY`** (default **0.32**), the app returns a fixed message and **skips the LLM**:

> “I could not find enough evidence in the uploaded document to answer this question.”

Tune with env var `RETRIEVAL_MIN_SIMILARITY`.

### Direct extraction and skipping the LLM

- **`direct_answer`** — beginning/ending modes pull text from chunks without calling the LLM.
- **`skip_llm_message`** — page/section not found, or weak semantic match; user gets a clear message instead of a guessed answer.

### Source grounding

Retrieval returns **`sources`**: `{chunk_index, page_number, chunk_text}` for each chunk used. These show up in the UI Source panel and in `messages.sources_json`. The LLM sees labeled chunks in its prompt, but user-facing citations come from retrieval, not from parsing the model output.

### Hybrid retrieval limits (MVP)

- Routing uses phrase/regex rules — odd wording may fall back to SEMANTIC.
- Page lookup needs page metadata (PDF/DOCX). TXT has no pages.
- Section lookup uses simple heading matching.
- Summary mode uses a subset of chunks, not the full file.

## Redis answer cache

- **Key:** `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}` (`normalized` = strip + lowercase for the key only)
- **Value:** JSON `{"answer": "...", "sources": [...]}`
- **TTL:** `CACHE_TTL_SECONDS` (default 3600)
- **Optional:** `ENABLE_REDIS_CACHE`. If Redis is off or errors, treat as cache miss — chat still works.
- **Not cached:** LLM errors and insufficient-context messages
- **Isolation:** keys include user id and document id

## Redis chat rate limit

Only on `POST /chat/{document_id}/ask` and `/ask/stream`. History, upload, and auth are not limited.

- **Key:** `rate:user:{user_id}:chat:{yyyyMMddHHmm}` (UTC minute)
- **Algorithm:** `INCR` + `EXPIRE 60`
- **Default cap:** 10/min when `ENABLE_RATE_LIMIT=true`
- **On exceed:** HTTP `429` with retry message
- **Fail-open:** if Redis is down, allow the request

## File storage layout

```
backend/storage/uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

Callers use `StorageBackend` (`storage/base.py`). Local disk now; S3 later without changing route code.

## Current limitations

- File types: PDF, TXT, DOCX only
- No OCR for scanned PDFs
- `.doc` not supported; DOCX parsing is basic
- BackgroundTasks ingestion (not durable)
- Local disk storage only
- One chat session per (user, document)
- Owner-only access (`document_permissions` unused)
- Rate limiting is optional MVP tooling, not real abuse prevention
- Query routing is rule-based, not learned
- No monitoring or audit logs

## Future work

Scaling paths are above. Other product gaps:

- Shared documents (schema exists; routes/UI not wired)
- Multi-document chat
- OCR for scanned PDFs
- More file types
- Cache invalidation on re-ingest
- Better ops (monitoring, audit logs)

### Multi-document Q&A (deferred)

**Today:** one document per chat session.

**Later:** search across a document set, new cache key shape, updated session model, UI to pick multiple docs.

The MVP does **not** change retrieval scope, cache keys, or chat routing for multi-doc support.

## Related docs

- [achieved-and-future-work.md](engineering-notes/achieved-and-future-work.md)
- [setup.md](setup.md)
- [api_design.md](api_design.md)
- [adr/](adr/)
- [engineering-notes/](engineering-notes/)

### ADR index

| ADR | Topic |
| --- | ----- |
| [0001](adr/0001-three-layer-architecture.md) | Three-layer architecture |
| [0002](adr/0002-postgres-pgvector.md) | PostgreSQL + pgvector |
| [0003](adr/0003-single-document-rag-scope.md) | Single-document scope |
| [0004](adr/0004-async-ingestion-backgroundtasks.md) | BackgroundTasks ingestion |
| [0005](adr/0005-redis-answer-cache.md) | Redis answer cache |
| [0006](adr/0006-alembic-migrations.md) | Alembic migrations |
| [0007](adr/0007-local-storage-vs-s3.md) | Local storage vs S3 |
