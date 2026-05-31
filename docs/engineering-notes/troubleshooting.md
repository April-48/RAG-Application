# Troubleshooting

Common local dev fixes. Not a production runbook.

---

## LLM 502 / “language model is unavailable”

- Check `OPENAI_API_KEY` in root `.env`
- Or set `LLM_BASE_URL` for a local server and make sure it is running
- Ingestion can still work while chat fails (different config)

## Document stuck on `processing`

Ingestion runs in the API process via BackgroundTasks. Large PDFs take time. If the server crashed mid-ingest, restart uvicorn — the document will stay stuck on `processing` until you manually delete and re-upload it.

## Redis down

Expected: app still works. Cache misses; rate limit skipped. Test with `docker compose stop redis`.

## Embedding dimension error

The embedding dimension in your config must match the DB column. Default is 384 (local MiniLM). Switching to OpenAI (1536) needs a new migration — see [known-limitations.md](known-limitations.md).

## Scanned PDF, empty answers

No OCR — use text-based PDF, TXT, or DOCX.

## RAG answers say “insufficient information” but sources look useful

Retrieval probably worked; the problem is usually downstream. See [rag_pipeline.md — Debugging insufficient-context answers](../rag_pipeline.md#debugging-insufficient-context-answers).

Quick checks:

1. **Stale Redis cache** — Clear chat history for that document, or set `ENABLE_REDIS_CACHE=false` while testing.
2. **Strict threshold** — Ensure `RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD=false` in `.env`, then restart middleware.
3. **Old chunks** — Re-upload the document after text-cleanup or embedding changes.
4. **Logs** — `docker compose logs -f middleware | grep -E "Retrieval|LLM prompt|Answer path"`

If logs show `LLM insufficient-context despite N chunks`, focus on prompt wording and chunk text quality (PDF boilerplate), not retrieval scope.

## Middleware fails to start (ImportError)

After RAG refactors, rebuild the middleware image — it does not mount source code:

```bash
docker compose up -d --build middleware
```

See [known-limitations.md](known-limitations.md) for MVP gaps.
