# API Design

This document describes the HTTP API exposed by the **middleware** (FastAPI). It matches the code in `middleware/app/routes/` and `middleware/app/schemas/`.

You can also open the live OpenAPI docs at `http://localhost:8000/docs`.

## Conventions

- **Base URL:** `/` (example: `http://localhost:8000`)
- **Auth:** protected routes need `Authorization: Bearer <token>`
- **Ownership:** Accessing another user's document returns `404`, not `403` — this way the API does not leak whether a document id exists.
- **JSON fields:** snake_case in request and response bodies
- **Errors:** `{ "detail": "<message>" }` with the matching HTTP status code

## Auth (`/auth`)

| Method | Path           | Auth | Description        |
| ------ | -------------- | ---- | ------------------ |
| POST   | `/auth/signup` | No   | Create a new user  |
| POST   | `/auth/login`  | No   | Get a JWT token    |
| GET    | `/auth/me`     | Yes  | Get current user   |

**POST `/auth/signup`**

```json
// request
{ "email": "user@example.com", "password": "secret123" }
// response 201
{ "id": "uuid", "email": "user@example.com", "created_at": "2026-01-01T00:00:00Z" }
```

- Password must be 8–128 characters.
- Returns `409` if the email is already registered.

**POST `/auth/login`**

```json
// request
{ "email": "user@example.com", "password": "secret123" }
// response 200
{ "access_token": "<jwt>", "token_type": "bearer" }
```

- Returns `401` if email or password is wrong.

**GET `/auth/me`**

```json
// response 200
{ "id": "uuid", "email": "user@example.com", "created_at": "2026-01-01T00:00:00Z" }
```

## Documents (`/documents`)

| Method | Path                           | Auth | Description                         |
| ------ | ------------------------------ | ---- | ----------------------------------- |
| POST   | `/documents/upload`            | Yes  | Upload a file (multipart)           |
| GET    | `/documents`                   | Yes  | List your documents                 |
| GET    | `/documents/{document_id}`     | Yes  | Get one owned document              |
| PATCH  | `/documents/{document_id}`     | Yes  | Rename display label                |
| GET    | `/documents/{document_id}/file`| Yes  | Download or open the original file  |
| DELETE | `/documents/{document_id}`     | Yes  | Delete document, chunks, and file   |

**POST `/documents/upload`** — send `multipart/form-data` with a `file` field.

Allowed file types: `.pdf`, `.txt`, `.docx`.

```json
// response 201
{
  "id": "uuid",
  "owner_id": "uuid",
  "filename": "report.pdf",
  "display_name": null,
  "file_type": "pdf",
  "visibility": "private",
  "status": "uploaded",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

Document status flow: `uploaded` → `processing` → `ready` (or `failed`). The upload response comes back immediately. Ingestion runs in the background after that.

**DELETE `/documents/{document_id}`** — returns **`204 No Content`** on success; removes the document row, chunks, and file on disk.

**PATCH `/documents/{document_id}`**

```json
// request
{ "display_name": "Q4 Report" }
// response 200 — same fields as DocumentResponse; file on disk is not renamed
```

## Chat / Q&A (`/chat`)

Chat is scoped to one document at a time. Every route takes a `{document_id}`. The document must be `ready` before you can ask questions.

| Method | Path                             | Auth | Rate limit | Description              |
| ------ | -------------------------------- | ---- | ---------- | ------------------------ |
| POST   | `/chat/{document_id}/ask`        | Yes  | Yes*       | One-shot answer + sources |
| POST   | `/chat/{document_id}/ask/stream` | Yes  | Yes*       | SSE stream               |
| GET    | `/chat/{document_id}/history`    | Yes  | No         | Chat history             |
| DELETE | `/chat/{document_id}/history`    | Yes  | No         | Clear chat history       |

\* Rate limit applies when `ENABLE_RATE_LIMIT=true` (`.env.example` sets `true`; code default is `false` without `.env`). Returns `429` when exceeded. If Redis is unavailable, the rate limit is skipped and the request goes through.

**POST `/chat/{document_id}/ask`**

```json
// request
{ "question": "What is the refund policy?" }
// response 200
{
  "answer": "…",
  "sources": [
    {
      "chunk_index": 0,
      "page_number": 2,
      "chunk_text": "…"
    }
  ]
}
```

- `404` — document missing or not owned by you
- `409` — document is not `ready` yet
- `502` — LLM call failed (when the pipeline reaches the LLM and it errors)

**Sources** come from the retrieval pipeline — not from the LLM reply. Each source has `chunk_index`, optional `page_number`, and `chunk_text`.

**POST `/chat/{document_id}/ask/stream`**

Same request body as `/ask`. Response type is **Server-Sent Events** (`text/event-stream`).

Each line looks like:

```json
{ "type": "token", "data": "partial answer text" }
{ "type": "sources", "data": [ { "chunk_index": 0, "page_number": 1, "chunk_text": "…" } ] }
{ "type": "done" }
```

On a cache hit, the server sends the full answer as one `token` event, then `sources`, then `done`.

If the LLM fails during streaming:

```json
{ "type": "error", "data": "The language model is unavailable" }
```

For hybrid retrieval, some questions skip the LLM (direct extraction or weak evidence when threshold enforcement is on). Those still use the same event shape: `token` → `sources` → `done`.

**Insufficient-context behavior:** returned when no chunks are retrieved, all chunks are empty/unusable, or the LLM determines context has no relevant information. If the UI shows useful sources but the answer is insufficient-context, see [rag_pipeline.md](rag_pipeline.md#debugging-insufficient-context-answers).

**GET `/chat/{document_id}/history`**

```json
// response 200
[
  {
    "id": "uuid",
    "role": "user",
    "content": "What is the refund policy?",
    "sources": [],
    "created_at": "2026-01-01T00:00:00Z"
  },
  {
    "id": "uuid",
    "role": "assistant",
    "content": "…",
    "sources": [
      { "chunk_index": 0, "page_number": 2, "chunk_text": "…" }
    ],
    "created_at": "2026-01-01T00:00:01Z"
  }
]
```

**DELETE `/chat/{document_id}/history`**

Clears all saved messages for this user + document. Also removes Redis answer-cache entries for the same pair when cache is enabled.

```json
// response 200
{ "deleted": 4, "cache_cleared": 2 }
```

- `deleted` — message rows removed from Postgres (0 if no session yet)
- `cache_cleared` — Redis keys removed (0 when cache is off or Redis is down)
- `404` — document missing or not owned by you

Uploaded files and vector chunks are **not** deleted.

## Health

| Method | Path      | Auth | Description  |
| ------ | --------- | ---- | ------------ |
| GET    | `/health` | No   | Basic liveness check — returns `ok` if the server is up |

```json
// response 200
{ "status": "ok" }
```

## Related docs

- [`rag_pipeline.md`](rag_pipeline.md) — ingest, retrieval, prompts, debugging
- [`setup.md`](setup.md) — how to run the app locally
- [`system_design.md`](system_design.md) — architecture, hybrid retrieval, data flows
