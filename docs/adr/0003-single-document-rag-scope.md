# ADR 0003: Single-document RAG scope for the MVP

## Status

Accepted (MVP)

## Context

RAG products can answer against **one selected document**, a **folder**, or **everything the user uploaded**. Each choice changes retrieval filters, cache key design, chat session modeling, UI, and how you explain citations in a demo.

For this MVP we prioritized a clear homework narrative: upload a file, wait until it is `ready`, select it in chat, ask questions grounded in that file, and show source chunks. Multi-document search is useful later but expands scope quickly.

## Decision

**MVP chat is scoped to one selected document per chat session.**

Concrete behavior in the codebase:

- Each `ChatSession` is tied to one `(user_id, document_id)` pair.
- Retrieval embeds the question and searches pgvector **only within that `document_id`** (`ChunkRepository.search_by_document`).
- Redis cache keys include `user_id` and `document_id`:  
  `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`.
- API routes are document-scoped: `POST /chat/{document_id}/ask`, `/ask/stream`, `GET /history`.
- UI: user picks a ready document in the chat sidebar; deep link `?doc=<uuid>` selects it on load.

**Multi-document Q&A is explicitly out of scope** for the MVP (deferred to future work in `system_design.md`).

## Alternatives Considered

| Alternative | Why deferred |
| ----------- | ------------ |
| Search all of a user’s documents by default | Harder to explain wrong citations; retrieval and cache keys must represent a document set. |
| Collection / folder scoped retrieval | Needs a collection model and UI we did not build. |
| Global corpus without a picker | Simpler UI but weak “grounded in this upload” story for grading and demos. |

## Rationale

- **Correctness and security:** If the user passes owner checks for a `document_id`, every retrieved chunk belongs to that document. Cross-document leakage is a smaller risk than multi-doc search across many ids.
- **Stable cache keys:** One document id per session keeps Redis entries predictable and aligned with ADR 0005.
- **Demo clarity:** The Source panel maps directly to one file; page numbers (PDF) and chunk text are easy to walk through in an interview.
- **Incremental path:** The pipeline already takes `document_id` as a parameter. Expanding scope later mainly touches retrieval filter, session model, cache fingerprint, and UI — not a full rewrite.

Sharing: the **`document_permissions`** table exists in the schema, but **owner-only access is what the app implements today** (`get_owned`, same 404 for missing vs unauthorized). Shared read access is not wired through routes or retrieval.

## Consequences

**Benefits**

- Straightforward end-to-end demo: Dashboard upload → Chat on that doc → citations.
- Simpler API and mental model for homework reviewers.
- Easier to reason about access control in interviews.

**Limitations**

- Users cannot ask one question that compares or synthesizes across two uploads in a single chat session.
- Research-style “search my whole library” is not available.
- Document sharing remains future work despite the permissions table stub.

## Future Improvements

- **Multi-document retrieval:** search across a stable document set (still owner-scoped), with cache keys based on a hash of sorted document ids.
- **Wire up `document_permissions`** for read-only sharing — requires authorization checks in services and retrieval, not just schema.
- UI to select one vs many documents when scope expands.
