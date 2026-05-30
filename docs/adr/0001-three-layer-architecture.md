# ADR 0001: Layered frontend / API / application architecture

## Status

Accepted (MVP)

## Context

This project needs three kinds of code: a browser UI, HTTP endpoints for auth and RAG, and a substantial Python core (Postgres, pgvector retrieval, file storage, optional Redis cache, LLM calls). We had to choose how to split those concerns without turning a homework MVP into a multi-service deployment.

Common options were a single FastAPI monolith with server-rendered pages, a separate “business logic” microservice behind the API, or letting the frontend talk to the database directly. None of those fit our goals: a modern React chat UI with SSE streaming, clear boundaries for interviews, and a setup that runs on one laptop with Docker Compose.

## Decision

Use a **logical three-layer layout** in the repo. In the MVP this is **not** three independently deployed services — it is separation of responsibilities inside one application stack.

1. **Frontend** — React (Vite + TypeScript, Tailwind). UI only: routing, forms, document list, chat, source panel. All data comes from HTTP calls to the API; no direct database or RAG logic.

2. **API layer** — FastAPI (`middleware/app/` in the repo). This is the HTTP server: route definitions, JWT authentication, Pydantic request/response validation, and mapping domain exceptions to status codes (e.g. `DocumentNotFoundError` → 404). Route handlers stay thin: validate input, call the application layer, return JSON or `FileResponse`.

3. **Application / core layer** — Python package `app` under `backend/`. Models, repositories, services, RAG pipeline (`loader` → split → embed → retrieve → prompt → LLM), storage backends, Redis answer cache, and the ingestion worker entrypoint. Installed editable via `pip install -e ./backend` and **imported in-process** by FastAPI as `from app.services...` — not exposed as a separate HTTP service in the MVP.

Typical request path: **browser → FastAPI route → service in `app` → Postgres / Redis / local files → response**.

## Alternatives Considered

| Alternative | Why we did not choose it for the MVP |
| ----------- | ------------------------------------ |
| FastAPI + Jinja/templates only | Poor fit for streaming chat UX and a component-based UI. |
| Separate HTTP “core service” behind FastAPI | Extra deployment, service-to-service auth, and latency without a real scale need yet. |
| Frontend → database directly | No secure place for JWT validation, RAG, or server-side file parsing. |
| One undifferentiated FastAPI file | Harder to explain layers in system design interviews and harder to test RAG without HTTP. |

## Rationale

- **Frontend/backend separation:** The frontend stays intentionally lightweight — presentation and API client code only. That makes the HTTP contract (`docs/api_design.md`, OpenAPI at `/docs`) the stable boundary you can demo with curl or Postman.
- **API vs application logic:** FastAPI owns transport concerns (status codes, multipart upload, SSE headers). The `app` package owns business rules (owner checks, ingestion status, retrieval scoped to `document_id`, cache keys). That matches how many production teams structure Python backends even before they split processes.
- **In-process import:** For local development and grading, one uvicorn process is enough. Editable install avoids `sys.path` hacks and lets scripts or tests import `app` without starting the server.
- **Interview story:** You can point to folders and say what each layer must *not* do (see README layer table) — a clear system-design answer without overclaiming microservices.

## Consequences

**Benefits**

- Repo layout matches the architecture diagram in `docs/system_design.md`.
- RAG and repositories are testable without HTTP.
- Frontend can be rebuilt or hosted statically (CDN) while the API stays on one origin — a realistic future split.

**Trade-offs**

- The **API layer and application/core layer share one Python process**. Heavy ingestion (BackgroundTasks) or a crash in embedding code affects the same uvicorn worker that serves chat.
- The application layer is **not independently scalable** until you extract workers or a separate service; horizontal scale today means scaling the whole API process together.
- The repo folder is still named `middleware/` for historical reasons; in documentation we refer to it as the **API layer** because FastAPI is the backend server in ordinary terminology.

## Future Improvements

- Move ingestion off the request process (see ADR 0004: Celery/RQ + Redis) while keeping the same `app` package and `ingest_document()` boundary.
- Optionally expose `app` as an internal HTTP or gRPC service if multiple clients or languages need it.
- Keep OpenAPI and `api_design.md` aligned when routes change so the frontend/API contract stays explicit.
