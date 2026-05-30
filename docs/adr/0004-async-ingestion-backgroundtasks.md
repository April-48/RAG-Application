# ADR 0004: Background ingestion with FastAPI BackgroundTasks

## Status

Accepted (MVP)

## Context

Ingestion parses PDF/TXT/DOCX, splits text, runs embeddings, and writes many `document_chunks` rows. That work can take seconds and should not block the upload HTTP response. Users expect status to move from `uploaded` → `processing` → `ready` (or `failed`) while the UI stays responsive.

We needed work to run after the upload response without operating a separate worker fleet for the homework MVP.

## Decision

After a successful upload, the **API layer** schedules **`ingestion_worker.ingest_document(document_id, owner_id)`** using FastAPI **`BackgroundTasks`**.

**Important:** `BackgroundTasks` is a **lightweight post-response task mechanism**, not a durable job queue. Tasks run after the HTTP response is sent, still inside the same uvicorn process. If the process exits before the task finishes, that work is not guaranteed to complete.

Flow:

1. `POST /documents/upload` saves the file, creates a `documents` row with status `uploaded`, returns immediately.
2. The background worker opens a **new SQLAlchemy session** (`SessionLocal()` in `ingestion_worker.py`). It does **not** reuse the request-scoped session from the upload handler, because that request has already completed and its session is closed.
3. The worker loads the owned document and calls `DocumentService.ingest()` → `RAGPipeline.ingest()`.
4. Status updates on the same row: `processing`, then `ready` or `failed`.
5. The frontend polls `GET /documents` about every 5 seconds while any document is `uploaded` or `processing`.

This is **not** a separate Celery/RQ worker container — it shares the API process (see ADR 0001).

## Alternatives Considered

- **Synchronous ingest in the upload handler** — simpler code, but risks timeouts and poor UX on larger PDFs.
- **Redis + Celery / RQ** — durable, retryable, and horizontally scalable; more infrastructure for local grading setups.
- **Dedicated ingestion microservice** — operational overhead the MVP user load does not justify.

## Rationale

- **Fast return on upload** — the client gets a document id and can poll status immediately.
- **Minimal infrastructure** — no extra worker image in Docker Compose for the demo path.
- **Queue-friendly boundary** — `ingest_document(document_id, owner_id)` is already the unit of work; replacing BackgroundTasks with a queue later should not rewrite the RAG pipeline.
- **UI simplicity** — progress lives on the `documents.status` column, so the poller does not care whether a BackgroundTask or a Celery job ran ingestion.

## Consequences

**Benefits**

- Easy local run: `./scripts/dev_setup.sh` + uvicorn.
- Same ingestion code path you would call from a real worker later.

**Limitations**

- **Not durable:** if uvicorn restarts during `processing`, the job may be lost and the document may remain stuck in `processing` until manual cleanup or re-upload.
- **Not fair queuing:** concurrent large uploads contend on one process; no retry or dead-letter handling.
- **Scalability:** ingestion capacity is tied to the API process until workers are extracted.

## Future Improvements

- Enqueue to Redis + Celery or RQ; run workers in separate processes or containers.
- Retries and dead-letter handling for failed ingests.
- Optional progress metadata (e.g. pages processed) if the UI needs finer feedback.
