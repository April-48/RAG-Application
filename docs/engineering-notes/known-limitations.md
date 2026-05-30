# Known limitations

This file documents the main MVP limitations so they are clear during demos, grading, and future planning. The app is a homework-scale project with scalability-aware design — not a fully production-hardened system.

---

## Single-document RAG only

Chat is scoped to **one selected document per session**. Retrieval, cache keys, and the UI assume one `document_id`. There is no “search across all my uploads” mode in the MVP.

---

## BackgroundTasks are not a durable queue

Ingestion uses FastAPI `BackgroundTasks` in the API process. If the server restarts during `processing`, work may be lost or status may stall. There is no retry queue, no dead-letter handling, and no horizontal worker scaling.

Future direction: Redis + Celery/RQ (see ADR 0004).

---

## Local storage is development-only

Files live under `backend/storage/uploads/` on disk. This is fine for laptops and local Docker demos. It is **not** suitable for multi-instance deployment without object storage or a shared volume.

Future direction: S3-compatible backend behind `StorageBackend` (see ADR 0007).

---

## Scanned PDFs unsupported without OCR

Only text extracted from PDF text layers is indexed. Camera scans and image-only pages produce little or no text, which leads to weak or empty retrieval. OCR is future work.

---

## DOCX extraction is basic

python-docx reads paragraphs and simple tables. Complex layouts, headers/footers, embedded images, and legacy `.doc` are not supported. Use `.docx`, not `.doc`.

---

## Embedding dimension is fixed to the current provider

The database column dimension must match the active embedder (384 for local MiniLM by default, 1536 for OpenAI). Switching providers requires a migration and **re-ingesting** all documents. Mixed dimensions in one database are not supported.

---

## Shared document permissions are future work

Migration `0001_initial` creates a `document_permissions` table, but **routes and UI do not use it**. Access is **owner-only** today; unauthorized access returns the same `404` as a missing document to avoid leaking existence.

---

## Other MVP gaps

- No rate limiting or audit logs (normal for this scope; not claimed elsewhere as shipped features).
- Redis cache is not invalidated on re-ingest — stale answers are possible until TTL.
- No automated OCR, virus scan, or content moderation on uploads.
- Chat deep links (`?doc=`) work for selecting a ready document, but edge cases such as a deleted document or lost access could use clearer UI handling.

For architecture context see [`../system_design.md`](../system_design.md) and the ADRs in [`../adr/`](../adr/).
