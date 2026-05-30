#!/usr/bin/env bash
# One-time (or repeat-safe) local development setup for the RAG MVP.
#
# Assumes:
#   - Docker runs ONLY Postgres (db) and Redis (redis) via docker compose.
#   - Middleware (FastAPI) and frontend (Vite) run on the HOST machine.
#
# Run from anywhere:
#   ./scripts/dev_setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> RAG Application — dev setup (project root: $ROOT)"
echo

# --- Prerequisites -----------------------------------------------------------
echo "==> Checking prerequisites..."

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is not installed or not on PATH." >&2
    exit 1
  fi
  echo "    OK: $1 ($("$1" --version 2>/dev/null | head -1 || echo found))"
}

require_cmd python3
require_cmd node
require_cmd npm
require_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' is not available. Install Docker Desktop or the Compose plugin." >&2
  exit 1
fi
echo "    OK: docker compose"

echo

# --- Environment files (never overwrite existing) ----------------------------
echo "==> Environment files..."

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    Created .env from .env.example"
  echo "    IMPORTANT: edit .env and set OPENAI_API_KEY before using chat."
else
  echo "    Skipped .env (already exists — not overwritten)"
fi

if [[ ! -f frontend/.env ]]; then
  cp frontend/.env.example frontend/.env
  echo "    Created frontend/.env from frontend/.env.example"
else
  echo "    Skipped frontend/.env (already exists — not overwritten)"
fi

echo

# --- Docker: db + redis only -----------------------------------------------
echo "==> Starting Docker infrastructure (db + redis)..."
docker compose up -d db redis
echo "    Waiting a few seconds for containers to become healthy..."
sleep 5
docker compose ps db redis
echo

# --- Python virtual environment ----------------------------------------------
echo "==> Python virtual environment (.venv)..."

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  echo "    Created .venv"
else
  echo "    .venv already exists"
fi

echo "==> Installing Python dependencies..."
# middleware/requirements.txt includes `-e ../backend`; pip must run from middleware/.
"$ROOT/.venv/bin/pip" install -q -U pip setuptools wheel
(cd middleware && "$ROOT/.venv/bin/pip" install -r requirements.txt)
echo "    Python deps installed (backend editable package + middleware)"
echo

# --- Frontend dependencies ---------------------------------------------------
echo "==> Installing frontend dependencies..."
(cd frontend && npm install)
echo "    npm install complete"
echo

# --- Database migrations -----------------------------------------------------
echo "==> Running Alembic migrations..."
(cd backend && "$ROOT/.venv/bin/alembic" upgrade head)
echo "    Database schema is up to date"
echo

# --- Done --------------------------------------------------------------------
echo "==> Setup complete!"
echo
echo "Next steps:"
echo
echo "  1. Edit .env if needed (especially OPENAI_API_KEY for chat)."
echo
echo "  2. Terminal A — start the middleware API:"
echo "       ./scripts/dev_start.sh"
echo "     Or manually:"
echo "       source .venv/bin/activate"
echo "       uvicorn middleware.app.main:app --reload --port 8000"
echo
echo "  3. Terminal B — start the frontend:"
echo "       cd frontend && npm run dev"
echo
echo "  4. Open http://localhost:5173 (API docs: http://localhost:8000/docs)"
echo
