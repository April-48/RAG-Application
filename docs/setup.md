# Local setup

How I run this project locally. Homework / MVP setup — not production.

Before a demo, see [demo checklist](engineering-notes/demo-checklist.md).

---

## Testing

### Backend (pytest)

```bash
cd backend
pip install -e .
pytest
```

There are **48 tests** covering auth, document ownership, hybrid retrieval, Redis cache keys, and mocked chat. Tests do **not** call real LLM or embedding APIs.

### Frontend

```bash
cd frontend
npm run build
```

This runs TypeScript check + production build. Full signup → upload → chat → sources is checked manually with the [demo checklist](engineering-notes/demo-checklist.md).

---

## Docker Compose (full stack)

Runs Postgres, Redis, API, and frontend in containers. The API container includes both FastAPI and the backend `app` package in one process.

### 1. Copy env

```bash
cp .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY` if you want real LLM answers. For Compose, `DATABASE_URL` / `REDIS_URL` in `.env.example` already use service names `db` and `redis`.

### 2. Build and start

**Scripts (recommended):**

```bash
chmod +x scripts/docker_setup.sh scripts/docker_start.sh scripts/docker_stop.sh
./scripts/docker_setup.sh    # first time: build, start, migrate
./scripts/docker_start.sh    # later restarts
./scripts/docker_start.sh --build  # after backend/RAG code changes
./scripts/docker_stop.sh     # stop (keeps volumes)
```

**Or manually:**

```bash
docker compose up --build -d
```

Wait until `db`, `redis`, and `middleware` are healthy.

### 3. Run migrations (manual, first time or after volume reset)

```bash
docker compose run --rm middleware bash -lc "cd /app/backend && alembic upgrade head"
```

Migrations do **not** run automatically when a container starts.

### 4. Open the app

| URL | Purpose |
| --- | ------- |
| [http://localhost:5173](http://localhost:5173) | Frontend |
| [http://localhost:8000/docs](http://localhost:8000/docs) | API docs |
| `GET http://localhost:8000/health` | Health check → `{"status":"ok"}` |

The browser talks to the API at `http://localhost:8000`.

### 5. Quick test

1. Sign up / log in
2. Upload a text-based PDF, TXT, or DOCX
3. Wait for `uploaded` → `processing` → `ready`
4. Ask a question in Chat; check streaming answer and sources
5. Open the original file from Dashboard or Chat
6. Ask the **same question twice** to demo Redis cache (keep Redis running)

### Docker troubleshooting

```bash
docker compose ps
docker compose logs middleware
docker compose down          # stop, keep volumes
docker compose down -v       # wipe DB/Redis/upload volumes
```

Uploads persist in the `uploads_data` volume. First ingest may take a while while the embedding model downloads.

---

## Host development (API on your laptop)

Use this if you run uvicorn and Vite on your machine, with only Postgres and Redis in Docker.

**Scripts:**

| Script | Purpose |
| ------ | ------- |
| `scripts/docker_setup.sh` | Full stack in Docker |
| `scripts/docker_start.sh` | Restart Docker stack |
| `scripts/docker_start.sh --build` | Rebuild middleware after backend code changes |
| `scripts/docker_stop.sh` | Stop Docker (keep volumes) |
| `scripts/dev_setup.sh` | Host dev: db/redis in Docker, install deps, migrate |
| `scripts/dev_start.sh` | Run uvicorn on :8000 |

See [scripts/README.md](../scripts/README.md). `dev_setup.sh` sets `DATABASE_URL` / `REDIS_URL` to **localhost**. `docker_setup.sh` uses **db** / **redis** service names.

### Prerequisites

| Tool | Version |
| ---- | ------- |
| Docker + Docker Compose | For full stack or db/redis only |
| Python | 3.10+ (3.12 in Docker images) |
| Node.js | 20+ |

**Two common setups:**

- **All in Docker:** `db`, `redis`, `middleware`, `frontend`
- **Hybrid:** Docker runs `db` + `redis`; FastAPI and Vite run on your laptop

---

## Environment variables

### Root `.env`

Copy from `.env.example` at the repo root. Used by middleware and backend.

```bash
cp .env.example .env
```

| Variable | Purpose | Notes |
| -------- | ------- | ----- |
| `DATABASE_URL` | Postgres | Use `localhost:5432` when API runs on host |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` on host |
| `JWT_SECRET_KEY` | JWT signing | Change from placeholder for anything beyond solo dev |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | Embeddings | Default: `local` / `sentence-transformers/all-MiniLM-L6-v2` / **384** |
| `RETRIEVAL_TOP_K` | Semantic retrieval | Default **8** chunks |
| `RETRIEVAL_MIN_SIMILARITY` | Similarity floor when enforcement is on | Default **0.20** |
| `RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD` | Pre-filter weak hits before LLM | Default **false** (MVP — LLM decides) |

**RAG tuning and debugging:** [rag_pipeline.md](rag_pipeline.md)
| `OPENAI_API_KEY` | LLM chat | Required unless you use a local OpenAI-compatible server |
| `LLM_MODEL` / `LLM_BASE_URL` | LLM config | Default `gpt-4o-mini`; set base URL for OpenRouter/Ollama |
| `ENABLE_REDIS_CACHE` | Answer cache | `true` in `.env.example`; code defaults to `false` without `.env` |
| `ENABLE_RATE_LIMIT` | Chat rate limit | On ask routes only; fail-open if Redis is down |
| `UPLOAD_DIR` | Upload folder | Default `backend/storage/uploads` |

**Postgres in docker-compose.yml:** user `postgres`, password `password`, database `rag_app`. Your `DATABASE_URL` must match.

**localhost vs Docker names:** use `localhost` when the API runs on your laptop; use `@db` and `@redis` when the API runs inside Compose.

### Frontend `frontend/.env`

Vite does not read the root `.env` for `VITE_*` keys.

```bash
cp frontend/.env.example frontend/.env
```

| Variable | Default |
| -------- | ------- |
| `VITE_API_BASE_URL` | `http://localhost:8000` |

---

## Start Postgres and Redis

From repo root:

```bash
docker compose up -d db redis
docker compose ps
```

Service names: **`db`** (Postgres + pgvector) and **`redis`**.

pgvector is created on first DB init via `infra/postgres/init/001_extensions.sql`.

### Reset database

If Postgres fails to start after a bad first init:

```bash
docker compose down -v
docker compose up -d db redis
cd backend && alembic upgrade head && cd ..
```

`down -v` wipes volumes — you will need to migrate again and re-upload documents.

---

## Run Alembic migrations

Schema changes go through Alembic (not `create_all` as the main path).

```bash
cd backend
alembic upgrade head
cd ..
```

Run after pulling new migrations or resetting the DB.

- Migrations live in `backend/alembic/versions/`.
- Default embeddings are **384** dimensions (local MiniLM). Switching to OpenAI 1536 needs a migration and re-ingest.

---

## Install dependencies

### Option A — setup script

```bash
chmod +x scripts/dev_setup.sh scripts/dev_start.sh
./scripts/dev_setup.sh
```

This script:

1. Creates `.env` and `frontend/.env` if missing (never overwrites)
2. Sets localhost URLs for host dev
3. Starts `db` and `redis` only
4. Creates `.venv` and installs Python deps
5. Runs `npm install` in frontend
6. Runs `alembic upgrade head`

### Option B — manual

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

## Start the API

**Terminal A** — from repo root:

```bash
./scripts/dev_start.sh
```

Or manually:

```bash
source .venv/bin/activate
uvicorn middleware.app.main:app --reload --port 8000
```

Check: [http://localhost:8000/health](http://localhost:8000/health)  
Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Set `OPENAI_API_KEY` (or a local LLM URL) before testing chat.

---

## Start the frontend

**Terminal B:**

```bash
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Demo test flow

1. Sign up and log in
2. Upload a text-based PDF, TXT, or DOCX
3. Watch status: `uploaded` → `processing` → `ready`
4. Open Chat, pick the document, ask a question — answer streams; sources show in the side panel
5. Ask the same question again — faster if Redis cache is on
6. Refresh the page — history should still load
7. Open the original file from Dashboard or Chat

Optional: second account trying the first user's document id → **404**.

Full list: [demo checklist](engineering-notes/demo-checklist.md).

---

## Troubleshooting

### LLM returns 502

- Set `OPENAI_API_KEY` in `.env`, or point `LLM_BASE_URL` at a running local server
- See [troubleshooting.md](engineering-notes/troubleshooting.md)

### Document stuck in `processing`

Ingestion runs in the API process. Large PDFs take time. Restart uvicorn if the server crashed mid-job.

### Redis / cache

- Cache is optional. Chat works with Redis stopped.
- For cache demo: `docker compose up -d redis` and `ENABLE_REDIS_CACHE=true`

### Embedding dimension errors

`EMBEDDING_DIM` must match the pgvector column (384 local, 1536 OpenAI). Re-upload after changing.

### Scanned PDFs

No OCR — use text-based PDF, TXT, or DOCX.

### Useful commands

```bash
docker compose down
docker compose down -v
docker compose ps
curl http://localhost:8000/health
```

More help: [troubleshooting.md](engineering-notes/troubleshooting.md), [known-limitations.md](engineering-notes/known-limitations.md).
