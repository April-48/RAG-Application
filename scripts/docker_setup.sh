#!/usr/bin/env bash
# First-time (or rebuild) Docker Compose full stack: db, redis, middleware, frontend.
#
# Run from anywhere:
#   ./scripts/docker_setup.sh
#
# After this, use ./scripts/docker_start.sh for restarts without rebuild.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/lib/env_urls.sh
source "$ROOT/scripts/lib/env_urls.sh"

echo "==> RAG Application — Docker full stack setup"
echo "    Project root: $ROOT"
echo

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose is not available." >&2
  exit 1
fi

echo "==> Environment file..."
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    Created .env from .env.example"
else
  echo "    Using existing .env"
fi
set_env_for_docker .env
echo "    Tip: set OPENAI_API_KEY in .env for real LLM chat."
echo

echo "==> Building and starting all services..."
docker compose up --build -d
echo

echo "==> Waiting for middleware health..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo

echo "==> Running Alembic migrations (manual step, not on container start)..."
docker compose run --rm middleware bash -lc "cd /app/backend && alembic upgrade head"
echo

docker compose ps
echo
echo "==> Docker setup complete!"
echo
echo "  Frontend:  http://localhost:5173"
echo "  API docs:  http://localhost:8000/docs"
echo "  Health:    http://localhost:8000/health"
echo
echo "  Logs:      docker compose logs -f middleware"
echo "  Stop:      ./scripts/docker_stop.sh"
echo "  Restart:   ./scripts/docker_start.sh"
echo
