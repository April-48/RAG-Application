# Achieved vs future work

What the app **does today** vs **product gaps** still open. For how the system
scales beyond local Docker Compose (API replicas, workers, S3, vector DB, etc.),
see the **Scalability beyond local development** section in [system design](../system_design.md).

---

## What is implemented (achieved)

### App quality

- Sign up / log in with JWT
- Upload PDF, TXT, DOCX
- Document lifecycle: `uploaded` → `processing` → `ready` / `failed` (frontend polls status)
- Select one document and chat with streaming SSE responses
- Answers include source snippets (chunk text, page when available)
- Open or download the original uploaded file
- Chat history persists per user + document
- Rename documents in the UI (`display_name`; file on disk unchanged)
- Search document list, deep link chat via `?doc=`
- Owner-only access — other users get `404`, not a leak of document existence

### System design / front–back separation

| Layer | Folder | Responsibility |
| ----- | ------ | ---------------- |
| Frontend | `frontend/` | React UI, routing, API calls only |
| API layer | `middleware/` | FastAPI routes, JWT auth, validation, HTTP errors |
| Application core | `backend/` (`app` package) | DB, RAG pipeline, storage, Redis cache, LLM/embeddings |

The API layer imports the core package in-process (`pip install -e ./backend`). That keeps local setup simple, but the boundaries match how I would split services later.

### Design choices that support scaling (details in system design)

- Docker Compose with separate db / redis / API / frontend services
- JWT auth (stateless API direction)
- Ingestion off the upload path (`BackgroundTasks` + `ingest_document()`)
- `StorageBackend` abstraction, Redis answer cache, Redis chat rate limit, Alembic migrations, owner-scoped repositories

---

## What is not implemented (product gaps)

These are feature or UX limits — not the full scaling story (see system design for that).

| Area | MVP today | Planned improvement |
| ---- | --------- | ------------------- |
| Document scope | Single-document chat | Multi-document retrieval and cache keys |
| Sharing | `document_permissions` table exists, unused | RBAC / shared access UI |
| PDF quality | Text layer only | OCR for scanned PDFs |
| File types | PDF, TXT, DOCX | PPTX, HTML, Markdown, etc. |
| Cache freshness | TTL-only invalidation | Invalidate cache on re-ingest |
| Ops | Optional Redis chat rate limit (fail-open MVP); no monitoring or audit logs | Production-grade abuse prevention, monitoring, audit logs |

---

## Related docs

- [System design](../system_design.md) — architecture, RAG flows, scalability table
- [Known limitations](known-limitations.md)
- [ADRs](../adr/) — why each MVP trade-off was chosen
