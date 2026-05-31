# ADR 0001: Three-layer architecture

## Status

Accepted (MVP)

## Context

I needed a UI, HTTP API, and Python core (Postgres, RAG, files, Redis, LLM) without needing three separate servers for a homework project.

## Decision

Three folders, one process today:

1. **Frontend** — React UI  
2. **API** (`middleware/`) — FastAPI routes + JWT  
3. **Backend** (`app/`) — business logic, RAG, DB  

Flow: browser → route → service → Postgres / Redis / files.

## Trade-offs

| Good | Bad |
| ---- | --- |
| Easy to explain and test | API + backend share one uvicorn process |
| Clear folder boundaries | API and backend share one process — needs splitting before it can scale |

## Future

If traffic grows, I would run multiple FastAPI instances behind a load balancer and move ingestion to worker processes (ADR 0004), without changing the three-folder layout.
