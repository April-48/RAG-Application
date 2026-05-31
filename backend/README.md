# Backend (core logic layer)

This folder holds the main business logic: database models, repositories, services, the RAG pipeline, storage, cache, and ingestion workers. The middleware API calls into this layer. This layer does not handle HTTP directly.

## Structure

```
app/
├── core/
│   ├── config.py          # Settings from environment
│   ├── exceptions.py      # Domain errors
│   └── security.py        # Password hashing
├── db/
│   ├── base.py            # SQLAlchemy base
│   └── database.py        # Engine + session (Postgres + pgvector)
├── models/
│   ├── user.py
│   ├── document.py
│   ├── chunk.py           # text + pgvector embedding
│   ├── chat_session.py
│   ├── message.py
│   └── document_permission.py  # schema only; unused in MVP
├── repositories/          # DB access (owner-scoped queries)
│   ├── user_repository.py
│   ├── document_repository.py
│   ├── chunk_repository.py
│   └── chat_repository.py
├── services/
│   ├── auth_service.py
│   ├── document_service.py
│   └── chat_service.py
├── rag/
│   ├── loader.py          # PDF / TXT / DOCX text extraction
│   ├── text_splitter.py   # Chunking
│   ├── embedding_service.py
│   ├── query_router.py    # Hybrid retrieval mode picker
│   ├── retrieval_service.py
│   ├── prompt_builder.py
│   ├── llm_service.py
│   └── pipeline.py        # Wires the stages together
├── cache/
│   ├── answer_cache.py    # Redis answer cache
│   ├── rate_limiter.py    # Chat rate limit
│   └── redis_client.py
├── storage/
│   ├── base.py            # StorageBackend interface
│   └── local_storage.py   # Local disk backend
└── workers/
    └── ingestion_worker.py  # BackgroundTasks entrypoint

alembic/                   # Database migrations
tests/                     # pytest suite (48 tests)
storage/                   # Runtime uploads (not a Python package)
└── uploads/               # {user_id}/{document_id}/<file>
```

## Design principles

- **Owner checks first** — every document has an `owner_id`; repositories only expose owner-scoped queries.
- **Scoped retrieval** — `query_router` + `RetrievalService`; vector search always filters by `document_id`.
- **Layering** — routes → services → repositories → DB.
- **Swappable parts** — storage, embeddings, LLM, and chunking sit behind interfaces so they can be swapped later.

## Where uploaded files go

```
backend/storage/uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

## Related docs

- [Setup guide](../docs/setup.md)
- [System design](../docs/system_design.md) — RAG flows and hybrid retrieval
- [ADRs](../docs/adr/)
