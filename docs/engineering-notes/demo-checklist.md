# Demo checklist

Run through this before presenting or recording. Assumes local setup from `README.md` / `scripts/dev_setup.sh`.

---

## Infrastructure

- [ ] **Postgres running** — `docker compose up -d db` (service name `db`); `docker compose ps` shows healthy.
- [ ] **Redis running** — `docker compose up -d redis` (optional for general use; **required for the cache demo** below).
- [ ] **Alembic migrations applied** — from `backend/`: `alembic upgrade head` (or re-run `dev_setup.sh` once).

---

## Application

- [ ] **FastAPI API server** — `uvicorn middleware.app.main:app --reload --port 8000`; `GET http://localhost:8000/health` → `{"status":"ok"}`.
- [ ] **Frontend** — `cd frontend && npm run dev`; open `http://localhost:5173`.
- [ ] **`.env` configured** — set `OPENAI_API_KEY` for OpenAI chat, or `LLM_BASE_URL` for a local/OpenAI-compatible server. Confirm `EMBEDDING_DIM` matches the pgvector column dimension (384 for local MiniLM by default).

---

## Auth

- [ ] **Sign up** a new user (or use a test account).
- [ ] **Log in** — JWT stored; navbar shows account; protected routes work.

---

## Documents

- [ ] **Upload** a PDF, TXT, and/or DOCX (pick at least one text-based PDF for reliable RAG).
- [ ] **Status flow** — list shows `uploaded` → `processing` → `ready` (poll ~5s); if `failed`, check file type and logs.
- [ ] **Open original file** — from Dashboard **View** or Chat header; PDF/TXT opens in tab, DOCX downloads.

---

## Chat / RAG

- [ ] **Select document** in chat sidebar (or land via `/chat?doc=<uuid>`).
- [ ] **Ask a question** answerable from the document text.
- [ ] **Streaming answer** — tokens appear via SSE (`/chat/{id}/ask/stream`).
- [ ] **Source citations** — Source panel shows chunk snippets (and page numbers for PDFs when available).
- [ ] **Chat history after refresh** — reload page; prior messages still load from `GET /chat/{id}/history`.

---

## Cache (optional but good to show)

- [ ] **Cache hit demo** — keep Redis running with `ENABLE_REDIS_CACHE=true`. Ask a question once to populate the cache, then ask the **exact same question** again; the second response should be faster and API logs should show a cache hit (`app.cache.*`).
- [ ] **Fail-open demo** — `docker compose stop redis`, ask a **new** question; chat should still work (cache miss, full RAG path). Restart Redis if you want to repeat the cache demo.

---

## Security smoke test

- [ ] **Second user cannot access first user's documents** — sign up another account; `GET /documents/{id}` and chat routes against the first user's document id should return **404**, not the other user's data. Use browser devtools, curl, or Postman if the UI does not expose direct document-id access.

---

## If something fails

See [`troubleshooting.md`](troubleshooting.md) and [`known-limitations.md`](known-limitations.md). Common demo blockers: missing API key, scanned PDF with no text, embedding dimension mismatch, document stuck in `processing` after an API restart.
