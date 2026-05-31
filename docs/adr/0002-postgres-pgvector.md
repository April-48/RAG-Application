# ADR 0002: PostgreSQL + pgvector

## Status

Accepted (MVP)

## Context

I need one database for users, documents, chat, and chunk vectors. Each question searches within one document only.

## Decision

Postgres 16 + pgvector (Docker service `db`).

- Default: **384-dim** vectors (local MiniLM)  
- OpenAI **1536** supported in code — needs migration + re-ingest  
- Semantic search: cosine distance, `document_id` filter, default top-k = **8** (`RETRIEVAL_TOP_K`)
- Hybrid retrieval also uses chunk metadata (pages, headings)

## Trade-offs

| Good | Bad |
| ---- | --- |
| One DB to set up and debug | Large document collections may need pgvector indexes or a dedicated vector DB |
| Chunks live next to document rows | Cannot mix embedding sizes |

## Future

For larger document collections I would add pgvector indexes in Postgres first. Only if that is still too slow would I look at a separate vector database.
