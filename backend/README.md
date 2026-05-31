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
├── rag/           loader, cleanup, splitter, embed, router, retrieve, prompt, LLM, pipeline
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

## RAG modules (`app/rag/`)

| Module | Role |
| ------ | ---- |
| `loader.py` | Parse PDF/TXT/DOCX, run text cleanup |
| `text_cleanup.py` | Remove boilerplate and repeated headers |
| `text_splitter.py` | Chunk pages (1000 / 200 overlap) |
| `embedding_service.py` | Local MiniLM or OpenAI embeddings |
| `query_router.py` | Rule-based question routing |
| `retrieval_service.py` | Hybrid chunk fetch + pgvector search |
| `prompt_builder.py` | Grounded LLM messages |
| `generation.py` | LLM call + context logging |
| `pipeline.py` | Ingest / retrieve / generate orchestration |

Details: [RAG pipeline](../docs/rag_pipeline.md)

## Docs

- [Setup](../docs/setup.md) · [System design](../docs/system_design.md) · [RAG pipeline](../docs/rag_pipeline.md) · [ADRs](../docs/adr/)
