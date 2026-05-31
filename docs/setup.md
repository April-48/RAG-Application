# Local setup

Step-by-step guide to run the RAG Document Q&A app on your machine. This is an
**MVP / student project** setup — not a production deployment guide.

For a pre-demo checklist, see [`engineering-notes/demo-checklist.md`](engineering-notes/demo-checklist.md).

---

## Testing

### Backend (pytest)

```bash
cd backend
pip install -e .
pytest
```

Covers auth, document ownership/isolation, RAG helper logic, Redis answer-cache keys, and mocked `ChatService` flows. Tests do **not** call real LLM or embedding APIs.

### Frontend

```bash
cd frontend
npm run build
```

Frontend validation is TypeScript check + production build. Full signup → upload → chat → sources flow is checked manually via [`engineering-notes/demo-checklist.md`](engineering-notes/demo-checklist.md).

---

## Docker Compose (full stack)

Run **Postgres, Redis, API, and frontend** in containers. The API container includes both the FastAPI layer and the in-process `app` backend package — there is no separate backend service.

### 1. Copy env

```bash
cp .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY` if you want real LLM answers. For Compose, `DATABASE_URL` / `REDIS_URL` in `.env.example` already use Docker service names (`db`, `redis`); the middleware service also sets these in `docker-compose.yml`.

### 2. Build and start

**Using scripts (recommended):**

```bash
chmod +x scripts/docker_setup.sh scripts/docker_start.sh scripts/docker_stop.sh
./scripts/docker_setup.sh    # first time: build, start, migrate
./scripts/docker_start.sh      # later restarts
./scripts/docker_stop.sh       # stop (keeps volumes)
```

**Or manually:**

```bash
docker compose up --build -d
```

Wait until `db`, `redis`, and `middleware` are healthy (frontend starts after middleware).

### 3. Run migrations (manual, first time or after volume reset)

```bash
docker compose run --rm middleware bash -lc "cd /app/backend && alembic upgrade head"
```

Migrations are **not** run automatically on container start.

### 4. Open the app

| URL | Purpose |
| --- | ------- |
| [http://localhost:5173](http://localhost:5173) | Frontend (Vite dev server) |
| [http://localhost:8000/docs](http://localhost:8000/docs) | API docs |
| `GET http://localhost:8000/health` | Health check → `{"status":"ok"}` |

The browser calls the API at `http://localhost:8000` (`VITE_API_BASE_URL` on the frontend container).

### 5. Quick test

1. Sign up / log in  
2. Upload a text-based PDF, TXT, or DOCX  
3. Wait for `uploaded` → `processing` → `ready`  
4. Ask a question in Chat; confirm streaming answer and sources  
5. Open original file from Dashboard or Chat  
6. Ask the **same question twice** (Redis cache demo — keep Redis running)  

### Docker troubleshooting

```bash
docker compose ps
docker compose logs middleware
docker compose down          # stop, keep volumes
docker compose down -v       # wipe DB/Redis/upload volumes
```

Uploads inside Compose persist in the `uploads_data` volume. Embedding model download on first ingest can take a while inside the middleware image.

---

## Host development (API + frontend on your machine)

Use this if you prefer `./scripts/dev_setup.sh` and running uvicorn/Vite directly while only Postgres/Redis run in Docker.

**Scripts:**

| Script | Purpose |
| ------ | ------- |
| `scripts/docker_setup.sh` | Full stack in Docker — build, start, migrate |
| `scripts/docker_start.sh` | Restart full Docker stack |
| `scripts/docker_stop.sh` | Stop Docker stack (keep volumes) |
| `scripts/dev_setup.sh` | Host dev — db/redis in Docker, install deps, migrate |
| `scripts/dev_start.sh` | Run uvicorn on host (:8000) |

`dev_setup.sh` sets `DATABASE_URL` / `REDIS_URL` to **localhost** when needed. `docker_setup.sh` uses **db** / **redis** service names (Compose also overrides these on the middleware container).

### Prerequisites

| Tool | Version / notes |
| ---- | ---------------- |
| Docker + Docker Compose | Full stack via `docker compose up` **or** db/redis only for host dev |
| Python | 3.12+ |
| Node.js | 20+ (for the Vite frontend) |

**How the pieces can run:**

- **All in Docker:** `db`, `redis`, `middleware` (API + `app` package), `frontend` — see [Docker Compose](#docker-compose-full-stack) above.
- **Hybrid (host dev):** Docker runs `db` + `redis` only; FastAPI and Vite run on your laptop.

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

**localhost vs Docker service names:** When the API runs on your **host**, use `localhost` in `DATABASE_URL` and `REDIS_URL`. When the API runs **inside Compose**, use `@db` and `@redis` (see `.env.example`).

For host dev with only db/redis in Docker, uncomment the localhost lines in `.env.example`.

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
2. Ensures `.env` uses **localhost** for DB/Redis (host dev).
3. Starts `db` and `redis` only (not middleware/frontend containers).
4. Creates `.venv` and installs Python deps (`pip install -e ../backend` via `middleware/requirements.txt`).
5. Runs `npm install` in `frontend/`.
6. Runs `alembic upgrade head`.

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
