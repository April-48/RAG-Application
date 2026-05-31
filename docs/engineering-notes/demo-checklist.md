# Demo checklist

Run through this list before presenting or recording. Assumes you already ran setup from `README.md` or `scripts/dev_setup.sh`.

---

## Infrastructure

- [ ] **Postgres running** — `docker compose up -d db`; `docker compose ps` shows healthy.
- [ ] **Redis running** — `docker compose up -d redis` (optional for basic chat; **needed for cache demo**).
- [ ] **Migrations applied** — from `backend/`: `alembic upgrade head` (or run `dev_setup.sh` once).

---

## Application

- [ ] **API server** — `uvicorn middleware.app.main:app --reload --port 8000`; `GET http://localhost:8000/health` → `{"status":"ok"}`.
- [ ] **Frontend** — `cd frontend && npm run dev`; open `http://localhost:5173`.
- [ ] **`.env` set up** — add `OPENAI_API_KEY` for OpenAI chat, or `LLM_BASE_URL` for a local server. Check `EMBEDDING_DIM` matches the database (384 for local MiniLM by default).

---

## Auth

- [ ] **Sign up** a new user (or use a test account).
- [ ] **Log in** — JWT saved; navbar shows account; protected pages work.

---

## Documents

- [ ] **Upload** a PDF, TXT, and/or DOCX (use a text-based PDF for reliable RAG).
- [ ] **Status flow** — list shows `uploaded` → `processing` → `ready` (polls about every 5s). If `failed`, check file type and logs.
- [ ] **Open original file** — from Dashboard **View** or Chat header. PDF/TXT opens in a tab; DOCX downloads.

---

## Chat / RAG

- [ ] **Select document** in chat sidebar (or open `/chat?doc=<uuid>`).
- [ ] **Ask a question** that the document can answer.
- [ ] **Streaming answer** — tokens appear via SSE (`/chat/{id}/ask/stream`).
- [ ] **Sources** — Source panel shows chunk text (and page numbers for PDFs when available).
- [ ] **Hybrid retrieval demos** (optional but good to show):
  - “What is the first sentence of the document?” → direct extraction, LLM skipped
  - “Summarize this document” → summary mode + LLM
  - “What is on page 2?” → page lookup (PDF with page metadata)
  - Ask an off-topic question → weak-evidence message, no made-up answer
- [ ] **Chat history after refresh** — reload the page; messages load from `GET /chat/{id}/history`.

---

## Cache (optional)

- [ ] **Cache hit** — keep Redis running with `ENABLE_REDIS_CACHE=true`. Ask a question once, then ask the **exact same question** again. The second answer should be faster; logs should show a cache hit (`app.cache.*`).
- [ ] **Fail-open** — `docker compose stop redis`, ask a **new** question. Chat should still work. Restart Redis if you want to repeat the cache demo.

---

## Security smoke test

- [ ] **Second user blocked** — sign up another account. Trying to access the first user's document id (via API or devtools) should return **404**, not the other user's data.

---

## If something fails

See [troubleshooting.md](troubleshooting.md) and [known-limitations.md](known-limitations.md).

Common blockers: missing API key, scanned PDF with no text, embedding dimension mismatch, document stuck in `processing` after an API restart.
