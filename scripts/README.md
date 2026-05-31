# Scripts

Helper scripts for running the RAG app locally. Run them from the repo root (or any directory — they `cd` to the project root automatically).

## Two modes

| Mode | Setup | Start | When to use |
| ---- | ----- | ----- | ----------- |
| **Docker full stack** | `./scripts/docker_setup.sh` | `./scripts/docker_start.sh` | Closest to “just run the app” — db, redis, API, frontend all in containers |
| **Host dev** | `./scripts/dev_setup.sh` | `./scripts/dev_start.sh` + `cd frontend && npm run dev` | Faster Python iteration — API runs on your machine with `--reload`; only db/redis in Docker |

See [docs/setup.md](../docs/setup.md) for env vars and troubleshooting.

## Docker scripts

| Script | Purpose |
| ------ | ------- |
| `docker_setup.sh` | First time (or full rebuild): create `.env`, build images, start stack, run migrations |
| `docker_start.sh` | Start or restart without rebuilding |
| `docker_start.sh --build` | **Rebuild middleware + frontend**, then start — use after backend/RAG code changes |
| `docker_stop.sh` | Stop containers (keeps volumes) |

### When to rebuild

The **middleware** container **does not mount** `backend/` or `middleware/` source code. Python changes are baked into the image at build time.

- Changed backend, RAG, or middleware code in **Docker mode** → `./scripts/docker_start.sh --build` (or re-run `docker_setup.sh`)
- Changed **frontend** code → usually hot-reloads via volume mount; rebuild if dependencies or Dockerfile changed
- Changed **only** `.env` → restart is enough: `./scripts/docker_start.sh`

Host dev (`dev_start.sh`) uses `uvicorn --reload`, so backend edits apply without rebuild.

## Host dev scripts

| Script | Purpose |
| ------ | ----- |
| `dev_setup.sh` | `.venv`, npm install, start db+redis, run migrations, set localhost URLs in `.env` |
| `dev_start.sh` | Run API on http://localhost:8000 |

## RAG debugging (Docker)

After asking questions in Chat:

```bash
docker compose logs -f middleware | grep -E 'Retrieval|LLM prompt|Answer path'
```

More detail: [docs/rag_pipeline.md](../docs/rag_pipeline.md)

## Shared helpers

- `lib/env_urls.sh` — switch `DATABASE_URL` / `REDIS_URL` between `@localhost` (host dev) and `@db` / `@redis` (Compose)
- `lib/docker_common.sh` — URLs and tips printed at the end of Docker scripts
