# Backend (core logic layer)

All reusable business logic lives here: database models, repositories, services,
the RAG pipeline, storage, and (future) workers. The middleware calls into this
layer; this layer never deals with HTTP.

## Structure

```
app/
├── core/
│   └── config.py          # Settings from environment
├── db/
│   ├── base.py            # SQLAlchemy declarative base
│   └── session.py         # Engine + session factory (Postgres + pgvector)
├── models/                # ORM models
│   ├── user.py            # User (owns documents)
│   ├── document.py        # Document (owner_id)
│   └── chunk.py           # DocumentChunk (text + pgvector embedding)
├── repositories/          # Data access (owner-scoped queries)
│   ├── user_repository.py
│   ├── document_repository.py
│   └── chunk_repository.py
├── services/              # Business logic / orchestration
│   ├── auth_service.py
│   ├── document_service.py
│   └── chat_service.py
├── rag/                   # RAG pipeline stages
│   ├── loader.py          # Text extraction
│   ├── chunker.py         # Text splitting
│   ├── embedder.py        # Embedding generation
│   ├── retriever.py       # Scoped vector search
│   ├── generator.py       # LLM answer generation
│   └── pipeline.py        # Stage orchestration
├── storage/               # File storage backends (code)
│   ├── base.py            # Storage interface
│   └── local.py           # writes to ../storage/uploads/{user_id}/{document_id}/
└── workers/               # Future async workers
    └── ingestion_worker.py

storage/                   # Runtime data (sibling to app/, not a Python package)
└── uploads/               # Uploaded files: uploads/{user_id}/{document_id}/
```

## Design principles

- **Ownership-first access control** — every document has an `owner_id`; repositories
  expose only owner-scoped queries.
- **Scoped retrieval** — vector search always filters by `document_id` and the
  authorized user.
- **Layering** — routes → services → repositories → DB. Each layer depends only on
  the one below it.
- **Swappable modules** — storage backends, embedding/LLM providers, and chunking
  strategies sit behind interfaces so they can change in isolation.

## Layout of stored files

```
backend/storage/uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

## Related docs

- [`docs/setup.md`](../docs/setup.md) — local setup (migrations, env, Docker)
- [`docs/system_design.md`](../docs/system_design.md) — RAG flows and data model
- [`docs/adr/`](../docs/adr/) — architecture decisions
