# ADR 0003: Single-document RAG scope

## Status

Accepted (MVP)

## Context

RAG apps can answer about one file, a folder, or everything a user uploaded. Each choice changes retrieval, cache keys, chat sessions, and the UI.

For this homework I focused on a simple story: upload one file, wait until `ready`, pick it in chat, ask questions, show source chunks. Multi-document search adds a lot of scope.

## Decision

**MVP chat is scoped to one document per session.**

In the code:

- Each `ChatSession` links one `user_id` and one `document_id`.
- Retrieval searches pgvector **only inside that document**.
- Redis cache keys include both ids:  
  `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`
- API routes: `POST /chat/{document_id}/ask`, `/ask/stream`, `GET /history`
- UI: user picks a ready document; `?doc=<uuid>` deep links

**Multi-document Q&A is out of scope** for the MVP (see system design future work).

The `document_permissions` table exists in the schema, but **only owner access is implemented**. Unauthorized access returns `404`.

## Alternatives considered

| Option | Why deferred |
| ------ | ------------ |
| Search all user docs by default | Harder citations; cache keys need a doc set |
| Folder/collection scope | Needs new models and UI |
| No document picker | Weak “grounded in this upload” demo story |

## Why this works

- Easier to keep retrieval and security correct.
- Cache keys stay simple (ADR 0005).
- Source panel maps cleanly to one file in demos.
- Pipeline already takes `document_id` — expanding later is localized.

## Limits

- Cannot compare two uploads in one chat session.
- No “search my whole library” mode.
- Sharing is not wired despite the permissions table.

## Future improvements

- Multi-document retrieval with cache keys based on a hash of document ids.
- Wire up `document_permissions` for read-only sharing.
- UI to pick one vs many documents.
