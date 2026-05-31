# ADR 0004: Background ingestion with FastAPI BackgroundTasks

## Status

Accepted (MVP)

## Context

Ingestion parses files, splits text, runs embeddings, and writes many chunk rows. That can take seconds. The upload HTTP response should return quickly while status moves `uploaded` → `processing` → `ready` (or `failed`).

I needed post-upload work without running a separate worker fleet for the homework MVP.

## Decision

After upload, the API schedules **`ingestion_worker.ingest_document(document_id, owner_id)`** using FastAPI **`BackgroundTasks`**.

**Important:** BackgroundTasks is **not** a durable queue. Tasks run after the HTTP response, still inside the same uvicorn process. If the process exits early, work may not finish.

Flow:

1. `POST /documents/upload` saves the file, creates a row with status `uploaded`, returns immediately.
2. Background task opens a **new DB session** (not the request session — that one is already closed).
3. Worker calls `DocumentService.ingest()` → `RAGPipeline.ingest()`.
4. Status updates: `processing` → `ready` or `failed`.
5. Frontend polls `GET /documents` about every 5 seconds while status is in progress.

This is **not** a separate Celery container — it shares the API process (ADR 0001).

## Alternatives considered

- **Sync ingest in upload handler** — risks timeouts on large PDFs.
- **Redis + Celery/RQ** — durable and scalable; more setup for grading.
- **Ingestion microservice** — too much ops for MVP load.

## Why this works

- Upload returns fast; UI can poll status right away.
- No extra worker image in Docker Compose for the demo path.
- `ingest_document(document_id, owner_id)` is already the unit of work for a real queue later.
- UI only cares about `documents.status` — poller does not need to know BackgroundTasks vs Celery.

## Limits

- Not durable: uvicorn restart during `processing` may lose the job or leave status stuck.
- No retry or dead-letter queue.
- Ingestion capacity is tied to the API process.

## Future improvements

- Enqueue to Redis + Celery or RQ; run workers in separate containers.
- Retries and dead-letter handling.
- Finer progress UI if needed (pages processed, etc.).
