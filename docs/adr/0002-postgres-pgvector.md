# ADR 0002: PostgreSQL 16 + pgvector

## Status

Accepted (MVP)

## Context

The app stores users, documents, chat messages, and many text chunks per document. Q&A needs similarity search over embeddings, always scoped to one document and one owner.

Options: Postgres without vectors, SQLite, or a separate vector database (Qdrant, Pinecone, etc.) synced with Postgres.

## Decision

Use **PostgreSQL 16** with **pgvector** in one database (Docker service `db`):

- Relational tables: users, documents, chat, messages, `document_permissions` (unused in MVP)
- Vectors: `document_chunks.embedding` as a pgvector column

**Default dimension:** **384** for local `all-MiniLM-L6-v2`. Migration `0001_initial.py` creates `Vector(384)`.

OpenAI `text-embedding-3-small` at **1536** is supported in code, but switching needs a migration and **re-ingesting all documents**. You cannot mix 384 and 1536 in the same column.

Retrieval uses pgvector cosine distance, filtered by `document_id`, `top_k = 5` by default.

Hybrid retrieval also uses chunk metadata (page numbers, headings) — not only pgvector. See system design for query router modes.

## Alternatives considered

| Option | Trade-off |
| ------ | --------- |
| Dedicated vector DB | More services and sync logic — too much for this MVP |
| SQLite | Weak for concurrent writes; no pgvector in our stack |
| Postgres without pgvector | Would push vectors elsewhere |
| Embeddings only in Redis | Not durable; wrong place for authoritative chunk storage |

## Why this works

- One database = one connection string, one place to debug.
- Document rows and chunk rows stay together; owner checks are simple.
- pgvector is enough for single-document Q&A with modest chunk counts in a demo.
- A vector DB could help later at larger scale.

## Limits

- Large chunk volumes may need HNSW/IVFFlat indexes or an external vector store.
- Provider switch = migration + re-ingest for dimension changes.
- pgvector extension is created in `infra/postgres/init/` on first DB init, not inside Alembic.

## Future improvements

- Add pgvector indexes when latency matters.
- Revisit a dedicated vector DB if retrieval becomes a bottleneck.
- Document the runbook: change `Vector(n)`, migrate, re-ingest.
