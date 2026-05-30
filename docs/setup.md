# Local setup

Step-by-step guide to run the RAG Document Q&A app on your machine. This is an
**MVP / student project** setup — not a production deployment guide.

For a pre-demo checklist, see [`engineering-notes/demo-checklist.md`](engineering-notes/demo-checklist.md).

---

## Prerequisites

| Tool | Version / notes |
| ---- | ---------------- |
| Docker + Docker Compose | Postgres and Redis run in containers |
| Python | 3.12+ |
| Node.js | 20+ (for the Vite frontend) |

**How the pieces run locally:**

- **Docker:** Postgres (`db`) and Redis (`redis`) only.
- **Host machine:** FastAPI middleware on port **8000**, React frontend on **5173**.

The backend is a Python package imported by the middleware — it is not a separate HTTP service in this setup.

---

## Environment variables

### Root `.env`

Copy from `.env.example` at the repo root. Used by the middleware and backend.

```bash
cp .env.example .env
```

| Variable | Purpose | Notes |
| -------- | ------- | ----- |
| `DATABASE_URL` | Postgres connection | Use `localhost:5432` when the API runs on your host (default in `.env.example`) |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` on host |
| `JWT_SECRET_KEY` | JWT signing | Change from the placeholder for anything beyond solo local dev |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | Embeddings | Default: `local` / `all-MiniLM-L6-v2` / **384** |
| `OPENAI_API_KEY` | LLM (chat) | **Required for chat** unless you use a local OpenAI-compatible server |
| `LLM_MODEL` / `LLM_BASE_URL` | LLM config | Default model `gpt-4o-mini`; set `LLM_BASE_URL` for OpenRouter/Ollama/etc. |
| `ENABLE_REDIS_CACHE` | Answer cache | `true` in `.env.example`; set `false` if you skip Redis |
| `UPLOAD_DIR` | Upload folder | Default `backend/storage/uploads` |

**Important:** Postgres credentials in `docker-compose.yml` are `postgres` / `password` / database `rag_app`. Your `DATABASE_URL` must match when connecting from the host.

**localhost vs Docker service names:** When uvicorn runs on your laptop, use `localhost` in `DATABASE_URL` and `REDIS_URL`. Use `@db` and `@redis` only if the middleware itself runs inside Compose.

### Frontend `frontend/.env`

Vite does **not** read the root `.env` for `VITE_*` keys.

```bash
cp frontend/.env.example frontend/.env
```

| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `VITE_API_BASE_URL` | API base URL | `http://localhost:8000` |

---

## Start Postgres and Redis (Docker Compose)

From the repo root:

```bash
docker compose up -d db redis
docker compose ps    # db and redis should be healthy
```

Compose service names are **`db`** (Postgres + pgvector) and **`redis`**.

The pgvector extension is created on first database init via `infra/postgres/init/001_extensions.sql`.

### Reset database (if Postgres fails to start)

If you see errors like “superuser password is not specified” from a bad first init:

```bash
docker compose down -v
docker compose up -d db redis
cd backend && alembic upgrade head && cd ..
```

`docker compose down -v` wipes volumes — you will need to migrate and re-upload documents.

---

## Run Alembic migrations

Schema changes are managed with Alembic (not `create_all` as the main path).

```bash
cd backend
alembic upgrade head
cd ..
```

Run this after pulling new migrations or resetting the DB volume.

- Migrations live in `backend/alembic/versions/`.
- Default chunk embeddings use **384 dimensions** (local MiniLM). Switching to OpenAI 1536-dim requires changing the migration column and **re-ingesting** all documents.

---

## Install dependencies

### Option A — setup script (recommended first time)

From the repo root:

```bash
chmod +x scripts/dev_setup.sh scripts/dev_start.sh
./scripts/dev_setup.sh
```

This script:

1. Creates `.env` and `frontend/.env` **only if missing** (never overwrites).
2. Starts `db` and `redis`.
3. Creates `.venv` and installs Python deps (`pip install -e ../backend` via `middleware/requirements.txt`).
4. Runs `npm install` in `frontend/`.
5. Runs `alembic upgrade head`.

### Option B — manual install

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env

docker compose up -d db redis

python3 -m venv .venv && source .venv/bin/activate
(cd middleware && pip install -r requirements.txt)
cd backend && alembic upgrade head && cd ..
(cd frontend && npm install)
```

---

## Start the FastAPI middleware

**Terminal A** — from repo root:

```bash
./scripts/dev_start.sh
```

Or manually:

```bash
source .venv/bin/activate
uvicorn middleware.app.main:app --reload --port 8000
```

Check: [http://localhost:8000/health](http://localhost:8000/health) → `{"status":"ok"}`  
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Edit `.env` and set `OPENAI_API_KEY` (or configure a local LLM) **before** testing chat.

---

## Start the React frontend

**Terminal B:**

```bash
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Demo test flow

Quick sanity check after setup:

1. **Sign up** and **log in**.
2. **Upload** a text-based PDF, TXT, or DOCX on the Dashboard.
3. Watch status: **uploaded → processing → ready** (frontend polls every ~5s).
4. Open **Chat**, select the document, **ask a question** — answer should **stream**; **sources** appear in the side panel.
5. **Ask the same question again** — should be faster if Redis cache is on (check API logs for cache hit).
6. **Refresh the page** — chat history should still load.
7. **Open original file** — View on Dashboard or Chat header (PDF/TXT in tab; DOCX downloads).

Optional isolation check: create a second account and try the first user's document ID → should get **404**.

Full checklist: [`engineering-notes/demo-checklist.md`](engineering-notes/demo-checklist.md).

---

## Troubleshooting

### LLM returns 502 / “The language model is unavailable”

- Set `OPENAI_API_KEY` in root `.env`, or point `LLM_BASE_URL` at a running local server.
- Confirm the provider is reachable from your machine.
- Ingestion can still work while chat fails (embeddings and LLM use different config).

More detail: [`engineering-notes/troubleshooting.md`](engineering-notes/troubleshooting.md).

### Document stuck in `processing` or upload feels slow

Ingestion runs in-process via FastAPI `BackgroundTasks` — heavy PDFs block the same API process. Wait for `ready`/`failed`, or restart uvicorn if the server crashed mid-job.

### Redis / cache

- Cache is **optional**. With Redis stopped or `ENABLE_REDIS_CACHE=false`, chat should still work (just no speedup on repeat questions).
- For cache demo: `docker compose up -d redis` and keep `ENABLE_REDIS_CACHE=true`.

### Embedding dimension errors

`EMBEDDING_DIM` must match the pgvector column (384 local default, 1536 for OpenAI). After changing provider, migrate if needed and re-upload documents.

### Scanned PDFs return empty or useless answers

We only extract text from PDF text layers — **no OCR**. Use a text-based PDF, TXT, or DOCX for demos.

### Common commands

```bash
docker compose down       # stop containers (keep data)
docker compose down -v    # stop and wipe DB/Redis volumes
docker compose ps         # check health
curl http://localhost:8000/health
```

### Still stuck?

- [`engineering-notes/troubleshooting.md`](engineering-notes/troubleshooting.md)
- [`engineering-notes/known-limitations.md`](engineering-notes/known-limitations.md)
