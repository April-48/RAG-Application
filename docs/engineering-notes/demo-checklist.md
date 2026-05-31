# Demo checklist

Things I check before a demo or submission video.

---

## Setup

- [ ] Postgres up: `docker compose up -d db`
- [ ] Redis up (for cache demo): `docker compose up -d redis`
- [ ] Migrations: `cd backend && alembic upgrade head`
- [ ] API: `uvicorn middleware.app.main:app --port 8000` → `/health` OK
- [ ] Frontend: `cd frontend && npm run dev` → :5173
- [ ] `.env` has `OPENAI_API_KEY` (or local LLM URL)

## Basic flow

- [ ] Sign up / log in
- [ ] Upload PDF or TXT
- [ ] Status reaches `ready`
- [ ] Ask a question → streaming answer + sources
- [ ] While answering: input and Send disabled, “AI is answering. Please wait…” shown, typing indicator visible
- [ ] While answering: document list in sidebar is locked (cannot switch docs)
- [ ] Try a content question (main idea, limitations, summarize)
- [ ] Refresh page → history still there
- [ ] Clear chat history → messages gone

## Upload validation (optional but good to mention)

- [ ] Upload a valid PDF/TXT/DOCX → accepted
- [ ] Rename a non-document file to `.pdf` and upload → **400** (content mismatch)
- [ ] Upload over size limit → **413** (default 20 MB)

See [troubleshooting.md](troubleshooting.md) if uploads fail unexpectedly.

## Nice to show (optional)

- [ ] Same question twice → Redis cache faster second time
- [ ] “First sentence of the document” → hybrid router, no LLM
- [ ] Second user cannot open first user's doc id (404)

If RAG answers look wrong: [rag_pipeline.md](../rag_pipeline.md) · [troubleshooting.md](troubleshooting.md)
