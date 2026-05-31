# Known limitations

This file lists the main MVP limits so they are clear during demos and grading. This is a homework-scale project — not a production-ready system.

For what **is** built and how it could scale later, see [achieved-and-future-work.md](achieved-and-future-work.md) and [system design](../system_design.md).

---

## Single-document RAG only

Chat works on **one selected document at a time**. Retrieval, cache keys, and the UI all assume one `document_id`. There is no “search all my uploads” mode in the MVP.

---

## BackgroundTasks is not a real queue

Ingestion uses FastAPI `BackgroundTasks` inside the API process. If the server restarts while a document is `processing`, the job may be lost or the status may get stuck. There is no retry queue or worker scaling.

Future direction: Redis + Celery/RQ (see ADR 0004).

---

## Local storage is for development

Files live under `backend/storage/uploads/` on disk. That is fine for local demos. It does **not** work well if you run multiple API servers without shared storage.

Future direction: S3-style backend behind `StorageBackend` (see ADR 0007).

---

## Scanned PDFs need OCR (not built)

We only read text from PDF text layers. Camera scans and image-only pages give little or no text, so retrieval is weak or empty.

---

## DOCX parsing is basic

python-docx reads paragraphs and simple tables. Complex layouts, headers/footers, embedded images, and old `.doc` files are not supported. Use `.docx`.

---

## Embedding size is tied to the provider

The database column size must match the embedder (384 for local MiniLM by default, 1536 for OpenAI). Switching providers needs a migration and **re-ingesting** all documents. You cannot mix different vector sizes in one database.

---

## Document sharing is not wired up

Migration `0001_initial` creates a `document_permissions` table, but **routes and UI do not use it**. Access is owner-only today. Unauthorized access returns the same `404` as a missing document.

---

## Hybrid query routing is rule-based

Before the LLM runs, a **query router** picks a retrieval mode based on simple phrase rules:

- document beginning / ending
- page lookup
- section lookup
- summary
- semantic pgvector search (default)

This helps with demo-style questions, but it has limits:

- Unusual wording may not match the rules and falls back to semantic search.
- **Page lookup** needs page metadata from PDF/DOCX. Plain TXT has no pages.
- **Section lookup** matches headings with simple rules — odd headings may miss.
- **Semantic mode** rejects weak matches below `RETRIEVAL_MIN_SIMILARITY` (default 0.32).
- Summary mode picks a subset of chunks, not the full document text.

---

## Other MVP gaps

- **Redis chat rate limiting** is optional and fail-open. It is not real abuse prevention.
- No monitoring or audit logs yet.
- Redis answer cache is not cleared on re-ingest — stale answers are possible until TTL.
- No OCR, virus scan, or content moderation on uploads.
- Chat deep links (`?doc=`) work for ready documents, but deleted or inaccessible docs could use clearer UI messages.

For more context see [system design](../system_design.md) and the [ADRs](../adr/).
