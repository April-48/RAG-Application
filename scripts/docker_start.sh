#!/usr/bin/env bash
# Start (or restart) the full Docker Compose stack without rebuilding images.
#
# Run from anywhere:
#   ./scripts/docker_start.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Starting Docker Compose stack (db, redis, middleware, frontend)..."
docker compose up -d

echo
echo "==> Waiting for API health..."
for _ in $(seq 1 20); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "    OK: http://localhost:8000/health"
    break
  fi
  sleep 2
done

docker compose ps
echo
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000/docs"
echo
