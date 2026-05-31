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
- [ ] Try a content question (main idea, limitations, summarize)
- [ ] Refresh page → history still there
- [ ] Clear chat history → messages gone

## Nice to show (optional)

- [ ] Same question twice → Redis cache faster second time
- [ ] “First sentence of the document” → hybrid router, no LLM
- [ ] Second user cannot open first user's doc id (404)

If RAG answers look wrong: [rag_pipeline.md](../rag_pipeline.md) · [troubleshooting.md](troubleshooting.md)
