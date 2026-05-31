# ADR 0005: Optional Redis answer cache

## Status

Accepted (MVP)

## Context

A full RAG request embeds the question, searches vectors, calls the LLM, and saves chat history. Asking the **same question twice** repeats all of that — slower and more expensive. I wanted a speed-up for demos without making Redis required for correctness.

## Decision

When `ENABLE_REDIS_CACHE=true` (default in `.env.example`), cache successful answers in **`ChatService`**.

- **Key:** `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`
- **Normalization (key only):** `question.strip().lower()` — only whitespace and casing; different wording is a different key.
- **Value:** JSON `{"answer": "...", "sources": [...]}`
- **TTL:** `CACHE_TTL_SECONDS` (default 3600)

On **cache hit:** return cached answer and sources; skip retrieval and LLM. Still save the assistant message to chat history.

On **miss**, disabled cache, or **Redis error:** run full RAG. The request must **not** fail because of cache.

**Not cached:** LLM failures and fixed insufficient-context messages.

Redis is for speed and cost — not for correctness.

## Alternatives considered

- **No cache** — simple; weak “ask twice” demo.
- **In-process LRU** — not shared across instances; lost on restart.
- **HTTP-level cache only** — does not fit auth, per-user keys, and chat history writes well.

## Why this works

- **Fail-open** — chat works with Redis stopped (see troubleshooting doc).
- Keys include `user_id` and `document_id` (ADR 0003).
- Simple normalization without semantic deduplication.
- Logs under `app.cache.*` show hits and misses during dev.

## Trade-offs

- **Stale answers** until TTL if document content changes — re-ingest does not clear cache today.
- Key does not include prompt version, model name, or retrieval settings — flush Redis manually after those change.
- “Hello?” and “hello?” match; different punctuation or wording does not.

## Future improvements

- Include prompt/model/retrieval version in the key.
- Invalidate on re-ingest or document delete.
- Update key design for multi-document scope (ADR 0003).
