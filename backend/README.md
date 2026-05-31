# Backend

Python core logic: models, repos, services, RAG pipeline, storage, cache, ingestion worker. The FastAPI layer calls this code; nothing here speaks HTTP directly.

## Main folders

```
app/
├── core/          config, errors, password hashing
├── db/            Postgres session
├── models/        User, Document, Chunk, Chat, Message
├── repositories/  owner-scoped DB queries
├── services/      auth, documents, chat
├── rag/           loader, splitter, embed, router, retrieve, LLM, pipeline
├── cache/         Redis cache + rate limit
├── storage/       local file backend
└── workers/       ingest_document() for BackgroundTasks

alembic/           migrations
tests/             48 pytest tests
storage/uploads/   runtime files (gitignored)
```

## Rules I followed

- Every document has `owner_id`; repos filter by owner  
- Retrieval always scoped to one `document_id`  
- Routes → services → repos → DB  

## Docs

- [Setup](../docs/setup.md) · [System design](../docs/system_design.md) · [ADRs](../docs/adr/)
