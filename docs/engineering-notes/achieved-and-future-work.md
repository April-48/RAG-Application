# Achieved vs future work

This file lists what the app **does today** and what is still **not built**. For scaling ideas (more API servers, workers, S3, etc.), see the scalability section in [system design](../system_design.md).

---

## What is implemented

### App features

- Sign up and log in with JWT
- Upload PDF, TXT, and DOCX
- Document status flow: `uploaded` → `processing` → `ready` / `failed` (frontend polls every ~5s)
- Pick one document and chat with streaming SSE answers
- Answers include source snippets (chunk text, page number when available)
- Open or download the original uploaded file
- Chat history saved per user + document
- Rename documents in the UI (`display_name`; the file on disk stays the same)
- Search the document list, deep link to chat with `?doc=`
- Owner-only access — other users get `404`, not a permission error that leaks the document id
- **Hybrid RAG retrieval** — query router with 6 modes + pgvector search; can skip the LLM for direct answers or weak evidence

### Front–back separation

| Layer | Folder | What it does |
| ----- | ------ | ------------ |
| Frontend | `frontend/` | React UI, routing, API calls only |
| API layer | `middleware/` | FastAPI routes, JWT, validation, HTTP errors |
| Backend / core | `backend/` (`app` package) | DB, RAG pipeline, storage, Redis cache, LLM/embeddings |

The API layer imports the backend package in the same process (`pip install -e ./backend`). That keeps setup simple, but the folder split is how I would separate services later.

### Design choices that help scaling later

- Docker Compose with separate db / redis / API / frontend services
- JWT auth (stateless API)
- Ingestion runs after upload (`BackgroundTasks` + `ingest_document()`)
- `StorageBackend` interface, Redis answer cache, Redis chat rate limit, Alembic migrations, owner-scoped repositories

---

## What is not implemented

These are product gaps, not the full scaling story (see system design for that).

| Area | MVP today | What I would add later |
| ---- | --------- | ---------------------- |
| Document scope | Single-document chat | Search across multiple documents |
| Sharing | `document_permissions` table exists but is unused | Shared access UI + RBAC |
| PDF quality | Text layer only | OCR for scanned PDFs |
| File types | PDF, TXT, DOCX | PPTX, HTML, Markdown, etc. |
| Cache freshness | TTL only | Clear cache on re-ingest |
| Ops | Optional Redis rate limit; no monitoring | Better abuse prevention, logs, audit trail |

---

## Related docs

- [System design](../system_design.md) — architecture, RAG flows, scalability
- [Known limitations](known-limitations.md)
- [ADRs](../adr/) — why I made each MVP trade-off
