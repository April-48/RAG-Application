# ADR 0005: Optional Redis (cache + rate limit)

## Status

Accepted (MVP)

## Context

I use Redis for two optional things: speed up repeat questions, and limit chat asks per minute. The app must keep working if Redis is unavailable.

## Decision

Two toggles (`true` in `.env.example`; code defaults `false` without `.env`):

**1. Answer cache** (`ENABLE_REDIS_CACHE`) — `ChatService` / `AnswerCache`

- Key: `rag:answer:{user_id}:{document_id}:{sha256(normalized_question)}`  
- Value: `{answer, sources}`, TTL default 3600s  
- Miss or error → full RAG path  
- Insufficient-context answers are **not** cached  
- **Clear chat history** removes all cache keys for that user + document  

**2. Rate limit** (`ENABLE_RATE_LIMIT`) — `ChatRateLimiter` in middleware on **ask** routes only (`/ask`, `/ask/stream`)

- Key: `rate:user:{user_id}:chat:{yyyyMMddHHmm}` (one counter per user per calendar minute)
- `INCR` + `EXPIRE 60`, cap 10/min, HTTP 429  

Both fail-open via `redis_client.py`.

## Trade-offs

| Good | Bad |
| ---- | --- |
| Nice cache demo; basic cost guard | Cache not auto-invalidated on chunk re-ingest — use Clear history or TTL |
| Optional — not required for correctness | Not production-grade rate limiting |

## Future

The same Redis instance could later serve as the Celery/RQ broker for ingestion workers (ADR 0004), so cache and queue would share one service in a small deployment.
