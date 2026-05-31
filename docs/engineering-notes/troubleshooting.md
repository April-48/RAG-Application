# Troubleshooting

Common fixes for local development and demos. This is **not** a production runbook.

---

## “The language model is unavailable” (502)

**What you see:** Chat returns HTTP 502, or the SSE stream sends an `error` event with that message.

**Common causes:**

1. **`OPENAI_API_KEY` missing or wrong** — check `.env` at the repo root.
2. **`LLM_BASE_URL` wrong** — if using Ollama or OpenRouter, the URL must match that server.
3. **`openai` package missing** — reinstall: `(cd middleware && pip install -r requirements.txt)`.
4. **Local LLM not running** — if you point at localhost, start Ollama (or your server) first.
5. **Network or quota** — provider rate limits or billing can show up as generic LLM errors in logs.

**What to check:**

- API logs when you send a chat message.
- Try a simple `POST /chat/{document_id}/ask` before debugging SSE.

**Note:** Ingestion (embeddings) can still work while chat fails if embedding and LLM use different keys or providers.

---

## Ingestion is slow or stuck on `processing`

**What you see:** Status stays on `processing` for a long time, or never reaches `ready` / `failed`.

**Why:** Upload returns quickly. Ingestion runs **after that** in the same API process via `BackgroundTasks`. Large PDFs and local embedding models use CPU on that process.

**What helps:**

- Wait for `ready` or `failed` before uploading many large files back-to-back.
- Use smaller, text-based PDFs for demos.
- Check status with `GET /documents`.
- Restart uvicorn if a document is stuck after a crash (known MVP limit).

**Not a bug for MVP:** There is no fair queue — multiple ingests share one process.

---

## Redis should not break the app

**Expected:** With Redis stopped or `ENABLE_REDIS_CACHE=false`, signup, upload, ingest, and chat should still work. Cache misses are treated as normal misses.

**If everything breaks:**

- Try chat with Redis stopped: `docker compose stop redis`.
- Check `.env` — `ENABLE_REDIS_CACHE` should not be required for startup.
- A bad `REDIS_URL` should log warnings under `app.cache.*`, not crash requests.

**Demo tip:** Start Redis before the cache demo. Ask the same question twice to show a cache hit. Stop Redis and ask a **new** question to show fail-open behavior.

---

## Embedding dimension mismatch

**Symptoms:** Ingestion fails, retrieval errors, or Postgres errors about vector size.

**Cause:** `EMBEDDING_DIM` does not match the pgvector column. Local MiniLM is **384**. OpenAI `text-embedding-3-small` is **1536**. Different sizes cannot be stored together.

**Fix:**

1. Pick one provider in `.env` and set the matching `EMBEDDING_DIM`.
2. Check the Alembic migration uses the same `Vector(n)` (see `0001_initial.py`).
3. **Re-upload or re-ingest** all documents after changing dimension.

Do not mix two embedding providers in one database.

---

## Scanned PDFs need OCR

**Symptoms:** Document reaches `ready` but has almost no text, or answers always say there is not enough information.

**Cause:** We extract text with PyMuPDF from text layers only. Scanned/image PDFs have no selectable text. OCR is not implemented.

**Workarounds for demos:**

- Use a PDF with real text (export from Word or Google Docs).
- Use `.txt` or `.docx` instead.
- Run OCR externally and upload the result.

See [known-limitations.md](known-limitations.md) — this is an MVP gap, not a config bug.
