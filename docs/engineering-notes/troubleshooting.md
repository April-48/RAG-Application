# Troubleshooting

Practical fixes for issues during local development and demos. This is not a production runbook.

---

## “The language model is unavailable” (502)

**What you see:** Chat returns HTTP 502, or the SSE stream sends an `error` event with that message.

**Common causes:**

1. **`OPENAI_API_KEY` missing or wrong** — check `.env` at the repo root. Required for OpenAI; some local OpenAI-compatible servers still need a dummy key.
2. **`LLM_BASE_URL` misconfigured** — if using Ollama or OpenRouter, the base URL must match what that server expects.
3. **`openai` package not installed** — reinstall deps: `(cd middleware && pip install -r requirements.txt)`.
4. **Local LLM not running** — if pointing at localhost, start Ollama (or your server) first.
5. **Network / quota** — provider rate limits or billing show up as generic LLM errors in logs.

**What to check:**

- API server logs when you send a chat message.
- `curl` the provider endpoint from the same machine (optional sanity check).
- Try a minimal one-shot ask (`POST /chat/{document_id}/ask`) before debugging SSE.

**Note:** Ingestion (embeddings) can work while chat fails if embedding and LLM use different providers or keys.

---

## Ingestion is slow or document stays in `processing`

**What you see:** Status stays on `processing` for a long time, or never reaches `ready` / `failed`. The UI may feel sluggish while another document ingests.

**Why:** Upload itself returns quickly; ingestion runs afterward in the **same API process** via `BackgroundTasks` (ADR 0004). Heavy PDFs and local embedding models use CPU on that process.

**What helps:**

- Wait for the current document to reach `ready` or `failed` before uploading many large files back-to-back.
- Use smaller, text-based PDFs for demos.
- Check `documents.status` via `GET /documents` — polling should show `processing` → `ready`.
- Restart uvicorn if a document is stuck in `processing` after a crash (known MVP limitation).

**Not a bug (for MVP):** There is no fair queue — concurrent ingests share one process.

---

## Redis should not be a hard dependency

**Expected behavior:** With Redis stopped or `ENABLE_REDIS_CACHE=false`, the app still signs up, uploads, ingests, and answers questions. Cache lookups fail open (treated as a miss).

**If something breaks entirely:**

- Confirm chat works with Redis stopped: `docker compose stop redis`.
- Check `.env`: `ENABLE_REDIS_CACHE` should not be required for startup.
- Bad `REDIS_URL` should log warnings under `app.cache.*`, not crash requests.

**Demo tip:** Start Redis **before** the cache demo. Ask a question once to populate the cache, then ask the **exact same question** again to show a cache hit. To demonstrate fail-open behavior, stop Redis and ask a **new** question — chat should still work.

---

## Embedding dimension mismatch

**Symptoms:** Ingestion fails, retrieval errors, or Postgres errors mentioning vector dimensions.

**Cause:** `EMBEDDING_DIM` / provider does not match the pgvector column. Default local model is **384** (`all-MiniLM-L6-v2`). OpenAI `text-embedding-3-small` is **1536**. Vectors of different sizes cannot be stored or compared together.

**Fix:**

1. Pick one provider in `.env` and set matching `EMBEDDING_DIM`.
2. Confirm the Alembic migration defines the same `Vector(n)` dimension as the active embedding provider (see `0001_initial.py` for the MVP default).
3. **Re-upload or re-ingest** all documents after a dimension change — old chunks are invalid.

Do not mix embeddings from two providers in one database.

---

## Scanned PDFs need OCR

**Symptoms:** Document reaches `ready` with empty or tiny text, or answers are always “not enough information.”

**Cause:** We extract text with PyMuPDF from text layers only. **Scanned/image-only PDFs** have no selectable text — OCR is not implemented.

**Workarounds for demos:**

- Use a PDF with real text (export from Word/Google Docs).
- Use `.txt` or `.docx` instead.
- Pre-process with an external OCR tool and upload the resulting PDF or text.

See [`known-limitations.md`](known-limitations.md) — this is an MVP gap, not a configuration bug.
