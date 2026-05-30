# ADR 0005: Optional Redis answer cache (fail-open)

## Status

Accepted (MVP)

## Context

A full RAG request embeds the question, searches pgvector, calls the LLM, and writes chat history. Asking the **same question twice** repeats that work — slower and more token cost. We wanted a speed-up for demos without making Redis a correctness dependency.

## Decision

When `ENABLE_REDIS_CACHE=true` (default in `.env.example`), use **Redis** to cache successful answers in **`ChatService`** (not at the raw HTTP layer).

- **Key:** `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`
- **Normalization (key only):** `question.strip().lower()` — handles surrounding whitespace and casing only; it does **not** treat paraphrases or semantically equivalent questions as the same (e.g. “summarize this” vs “give me a summary” are different keys).
- **Value:** JSON `{"answer": "...", "sources": [...]}`
- **TTL:** `CACHE_TTL_SECONDS` (default 3600)

On **cache hit:** return cached answer and sources; skip retrieval and LLM. **`ChatService` still persists the assistant message** to chat history (implemented in both `ask()` and `ask_stream()`), so a repeat question still appears in the conversation after refresh.

On **miss**, disabled cache, or **any Redis error:** run the full RAG path. The request must **not** fail because of cache.

**Not cached:** LLM failures and the fixed insufficient-context message from `prompt_builder`.

Redis improves **latency and cost** for repeated questions; it is **not required** for the app to answer correctly.

## Alternatives Considered

- **No cache** — simplest; weak demo for “ask the same question again.”
- **In-process LRU** — no extra service, but not shared across instances and lost on restart.
- **HTTP-level cache only** — would not align cleanly with auth, per-user keys, and chat history writes in `ChatService`.

## Rationale

- **Fail-open** — chat, upload, and auth work with Redis stopped (`docs/engineering-notes/troubleshooting.md`).
- **Isolation** — keys include `user_id` and `document_id`, aligned with single-document scope (ADR 0003).
- **Sensible MVP scope** — one clear normalization rule without building semantic deduplication.
- Logging under `app.cache.*` makes hits and fallbacks visible during development.

## Consequences

**Benefits**

- Faster repeat questions in demos; fewer LLM calls.
- Shows an optional acceleration layer without coupling correctness to Redis.

**Trade-offs**

- **Stale answers** until TTL if document content changes — re-ingest does not invalidate keys today.
- **Key scope is narrow** — the key does not yet include prompt version, LLM model name, or retrieval parameters (`top_k`, etc.). After changing the prompt template, model, or retrieval settings, you may need to **flush Redis manually** to avoid serving old answers.
- **Casing-only normalization** — “Hello?” and “hello?” match; different punctuation or wording does not.

## Future Improvements

- Include prompt/model/retrieval version in the cache key or invalidate on config change.
- Invalidate keys on re-ingest, delete, or document update.
- Extend key design if multi-document scope is added (ADR 0003).
