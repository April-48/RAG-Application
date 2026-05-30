# API Design

Planned HTTP API exposed by the **middleware** (FastAPI). This is a design draft — no
endpoints are implemented yet. All request/response bodies are JSON.

## Conventions

- **Base URL:** `/` (e.g. `http://localhost:8000`)
- **Auth:** Bearer JWT in the `Authorization` header for all routes except register/login.
- **Ownership:** every document route is scoped to the authenticated user; accessing
  another user's resource returns `404` (not `403`) to avoid leaking existence.
- **Errors:** standard problem shape `{ "detail": "<message>" }` with appropriate HTTP status.

## Auth (`/auth`)

| Method | Path             | Auth | Description                          |
| ------ | ---------------- | ---- | ------------------------------------ |
| POST   | `/auth/register` | No   | Create a new user.                   |
| POST   | `/auth/login`    | No   | Exchange credentials for a JWT.      |

**POST `/auth/register`**

```json
// request
{ "email": "user@example.com", "password": "secret" }
// response 201
{ "id": "uuid", "email": "user@example.com" }
```

**POST `/auth/login`**

```json
// request
{ "email": "user@example.com", "password": "secret" }
// response 200
{ "access_token": "<jwt>", "token_type": "bearer" }
```

## Documents (`/documents`)

| Method | Path               | Auth | Description                                   |
| ------ | ------------------ | ---- | --------------------------------------------- |
| POST   | `/documents`       | Yes  | Upload a document (multipart). Owned by user. |
| GET    | `/documents`       | Yes  | List the current user's documents.            |
| GET    | `/documents/{id}`  | Yes  | Get one document (owner-scoped).              |
| DELETE | `/documents/{id}`  | Yes  | Delete a document and its chunks/files.       |

**POST `/documents`** — `multipart/form-data` with a `file` field.

```json
// response 201
{
  "id": "uuid",
  "ownerId": "uuid",
  "filename": "report.pdf",
  "status": "processing",
  "createdAt": "2026-01-01T00:00:00Z"
}
```

Document `status`: `uploaded` → `processing` → `ready` (or `failed`).

## Chat / Q&A (`/chat`)

| Method | Path     | Auth | Description                                                  |
| ------ | -------- | ---- | ----------------------------------------------------------- |
| POST   | `/chat`  | Yes  | Ask a question answered from the user's authorized documents. |

**POST `/chat`**

```json
// request
{
  "question": "What is the refund policy?",
  "documentIds": ["uuid"]        // optional; defaults to all of the user's docs
}
// response 200
{
  "answer": "…",
  "citations": [
    { "documentId": "uuid", "chunkId": "uuid", "snippet": "…" }
  ]
}
```

Retrieval is **always** filtered by `documentId` and the authenticated user. Any
`documentIds` not owned by the user are rejected before retrieval.

## Health

| Method | Path      | Auth | Description        |
| ------ | --------- | ---- | ------------------ |
| GET    | `/health` | No   | Liveness check.    |

## Related docs

- [`setup.md`](setup.md) — local install and running the stack.
- [`system_design.md`](system_design.md) — architecture, data model, and data flows.
