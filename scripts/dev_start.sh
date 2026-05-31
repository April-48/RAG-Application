#!/usr/bin/env bash
# Start the FastAPI middleware on the host machine (port 8000).
#
# Prerequisites:
#   ./scripts/dev_setup.sh   (host dev — db/redis in Docker)
#
# Full stack in Docker instead:
#   ./scripts/docker_start.sh
#
# Start the frontend separately in another terminal:
#   cd frontend && npm run dev
#
# Run from anywhere:
#   ./scripts/dev_start.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "ERROR: .venv not found. Run ./scripts/dev_setup.sh first." >&2
  exit 1
fi

# Quick check: db/redis should be up for host dev
if ! docker compose ps db redis 2>/dev/null | grep -q "(healthy)"; then
  echo "WARNING: db/redis may not be healthy. Try: docker compose up -d db redis" >&2
fi

echo "==> Starting middleware API on http://localhost:8000"
echo "    (Ctrl+C to stop)"
echo
echo "    Start the frontend in another terminal:"
echo "      cd frontend && npm run dev"
echo
echo "    Full Docker stack? Use ./scripts/docker_start.sh instead."
echo

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
exec uvicorn middleware.app.main:app --reload --port 8000
