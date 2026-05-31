# ADR 0003: Single-document RAG scope

## Status

Accepted (MVP)

## Context

RAG can search one file, a folder, or everything. For this project I kept it to **one selected document** to keep the demo and access control simple.

## Decision

- One `ChatSession` per (user, document)  
- Retrieval + Redis cache keys include that `document_id`  
- Routes: `/chat/{document_id}/ask`, `/ask/stream`, `/history`, `DELETE .../history`  
- Owner-only access today (`404` for others)

## Trade-offs

| Good | Bad |
| ---- | --- |
| Clear citations in the UI | No cross-file questions |
| Simple cache keys | No “search my library” |

## Future

Multi-document retrieval would need new session model, cache keys, and UI — out of scope for this MVP.
