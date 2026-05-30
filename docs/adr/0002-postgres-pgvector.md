# ADR 0002: PostgreSQL 16 + pgvector for relational data and embeddings

## Status

Accepted (MVP)

## Context

The app persists users, document metadata, chat sessions, messages, and many text chunks per document. Question answering needs **similarity search** over chunk embeddings, always scoped to one document and one owner. We had to pick where vectors live relative to relational data.

Options included Postgres without vectors, SQLite for local dev, or a dedicated vector database (Qdrant, Pinecone, Weaviate, etc.) synced with Postgres for metadata.

## Decision

Use **PostgreSQL 16** with the **pgvector** extension. All MVP tables live in one Postgres instance (Docker Compose service `db`):

- Relational: `users`, `documents`, `chat_sessions`, `messages`, `document_permissions` (schema present; sharing not wired in the MVP).
- Vectors: `document_chunks.embedding` as a pgvector column.

**Embedding dimension (important):** The current MVP schema is designed around **`vector(384)`** for the default local model **`all-MiniLM-L6-v2`** (`EMBEDDING_PROVIDER=local`). Migration `0001_initial.py` creates `Vector(384)`; the ORM reads `EMBEDDING_DIM` from settings but the database column size must match.

Switching to OpenAI **`text-embedding-3-small`** at **1536 dimensions** is supported in code via env config, but it is **not** a drop-in config change: you need an Alembic migration to alter `Vector(384)` → `Vector(1536)` (or equivalent) and **re-ingest every document**. Mixed 384- and 1536-dimensional vectors in the same column are invalid.

Retrieval uses pgvector **cosine distance**, filtered by `document_id`, `top_k = 5` (configurable via settings).

## Alternatives Considered

| Alternative | Trade-off |
| ----------- | --------- |
| **Dedicated vector DB** | Can scale similarity search further, but adds another service, sync logic, and ops burden — heavy for a homework MVP that already runs Postgres in Docker. |
| **SQLite** | Easy locally, weak for concurrent writers and no pgvector parity in our stack. |
| **Postgres without pgvector** | Would push vectors elsewhere or use naive scans; awkward for a RAG MVP focused on one DB story. |
| **Store embeddings only in Redis** | Not durable, wrong tool for authoritative chunk storage and joins with `documents`. |

## Rationale

- **One database** simplifies Alembic migrations, local setup (`docker compose up -d db`), and debugging — one connection string, one place to inspect rows.
- **Joins and ownership:** Document rows and chunk rows stay in the same DB. Repositories enforce `owner_id`; retrieval adds `WHERE document_id = :id`. No cross-store consistency problem for the MVP.
- **MVP-scale retrieval:** For single-document Q&A with modest chunk counts per file, pgvector sequential scan (no HNSW index yet) is acceptable. This is enough to demo RAG correctly; it is not a claim that pgvector alone handles massive multi-tenant corpora without tuning.
- **Vector DB later:** A dedicated store may help at large scale or specialized indexing, but for this project the complexity cost outweighed the benefit before core RAG flows worked end-to-end.

## Consequences

**Benefits**

- Fewer moving parts in Docker Compose (Postgres + optional Redis).
- Transactional semantics when updating document status and inserting chunks during ingestion.
- Familiar SQL and Alembic for schema reviews and interviews.

**Limitations**

- **Not all production workloads** stay on unindexed pgvector forever; large chunk volumes may need **HNSW or IVFFlat** indexes or an external vector store.
- **Provider switch = migration + re-ingest** for dimension changes (384 ↔ 1536).
- pgvector extension is created in `infra/postgres/init/` on first DB init, not inside Alembic — fresh environments must use that init path or create the extension manually.

## Future Improvements

- Add pgvector indexes when chunk counts or latency justify it.
- Revisit a dedicated vector DB if retrieval becomes a bottleneck after indexing.
- Document a runbook: change `Vector(n)`, run migration, clear chunks, re-ingest all documents.
