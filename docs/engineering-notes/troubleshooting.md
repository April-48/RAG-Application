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

See [known-limitations.md](known-limitations.md) for MVP gaps.
