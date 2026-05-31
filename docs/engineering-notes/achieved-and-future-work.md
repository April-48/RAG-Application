# Achieved vs future work

For a fuller scaling write-up, see [system design](../system_design.md#scalability-mvp--production).

---

## What I built

**Core homework flow**

- Sign up / log in (JWT)
- Upload PDF, TXT, DOCX
- Wait for `uploaded` → `processing` → `ready`
- Chat on one document with streaming answers and source snippets
- Chat history per user + document

**Extras I added on top**

- Hybrid RAG (query router + pgvector)
- RAG quality pass: text cleanup at ingest, grounded-but-flexible prompts, retrieval logging, configurable top-k / similarity threshold
- Clear chat history (Postgres messages + Redis cache for that document)
- Optional Redis cache and chat rate limit
- Rename documents, search list, open original file, `?doc=` deep link
- Owner-only access (other users get 404)

**Architecture**

| Layer | Folder | Role |
| ----- | ------ | ---- |
| Frontend | `frontend/` | UI only |
| API | `middleware/` | FastAPI routes + auth |
| Backend | `backend/` | RAG, DB, storage |

All three live in one repo. The API imports the backend directly in one process — easy for local development, easy to split later.

---

## What I did not build

- Multi-document chat (one file at a time only)
- Document sharing (`document_permissions` table unused)
- OCR for scanned PDFs
- Durable background queue — ingestion uses FastAPI BackgroundTasks today, not Celery/RQ
- Production monitoring / audit logs

---

## If I scaled this later

The MVP runs on one machine, but I split the main parts so they can scale on their own.

**Ingestion workers** — The upload flow already calls `ingest_document()` as a background task. Switching to Celery/RQ means enqueuing that job to Redis instead, so ingestion survives API restarts and can run in parallel.

**S3 for uploads** — Local disk works for Docker on a laptop. For multiple API instances I would plug an S3 backend into `StorageBackend` without rewriting the upload flow.

**More API instances** — The API is stateless (identity is in the JWT, state is in Postgres/Redis), so adding more containers behind a load balancer is straightforward.

**Stronger vector search** — pgvector in Postgres is fine for homework-scale data. At larger scale I would add indexes or move vectors to a dedicated DB.

I would tackle those four areas before things like OCR or multi-document search. Details and a target diagram are in [system design](../system_design.md).

---

## Related docs

- [RAG pipeline](../rag_pipeline.md) — retrieval, prompts, debugging
- [System design](../system_design.md)
- [Known limitations](known-limitations.md)
- [ADRs](../adr/)
