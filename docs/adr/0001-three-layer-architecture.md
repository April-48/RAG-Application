# ADR 0001: Three-layer architecture (frontend / API / backend)

## Status

Accepted (MVP)

## Context

This project needs three kinds of code: a browser UI, HTTP endpoints, and Python core logic (Postgres, pgvector, files, Redis, LLM). I had to split these without turning a homework MVP into multiple deployed services.

Options I considered: one FastAPI app with server-rendered pages, a separate microservice behind the API, or letting the frontend talk to the database directly. None fit well — I wanted React with SSE streaming, clear layers for interviews, and a setup that runs on one laptop.

## Decision

Use a **three-layer layout** in one repo. In the MVP this is **not** three separate servers — it is folder separation inside one stack.

1. **Frontend** — React (Vite + TypeScript + Tailwind). UI only. All data comes from HTTP calls.

2. **API layer** — FastAPI (`middleware/app/`). Routes, JWT auth, Pydantic validation, HTTP status codes. Route files stay thin and call the backend package.

3. **Backend / core** — Python package `app` under `backend/`. Models, repos, services, RAG pipeline, storage, cache, ingestion worker. Installed with `pip install -e ./backend` and imported in the same process as FastAPI.

Typical path: **browser → FastAPI route → backend service → Postgres / Redis / files → response**.

## Alternatives considered

| Option | Why not for MVP |
| ------ | --------------- |
| FastAPI + templates only | Bad fit for streaming chat UX |
| Separate HTTP core service | Extra deployment and latency without real need yet |
| Frontend → database | No safe place for JWT, RAG, or file parsing |
| One big FastAPI file | Hard to explain layers and test RAG without HTTP |

## Why this works

- Frontend stays lightweight — the HTTP contract is the boundary.
- FastAPI handles transport; the `app` package handles business rules.
- One uvicorn process is enough for local dev and grading.
- Easy to explain in interviews: each folder has a clear job.

## Trade-offs

- API and backend share one Python process. Heavy ingestion or a crash can affect chat on the same worker.
- Backend is not independently scalable until you extract workers or a separate service.
- The folder is named `middleware/` for history; in docs I call it the **API layer**.

## Future improvements

- Move ingestion to Celery/RQ (ADR 0004) while keeping the same `app` package.
- Optionally expose `app` as an internal HTTP service later.
- Keep `api_design.md` and OpenAPI in sync when routes change.
