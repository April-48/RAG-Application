#!/usr/bin/env bash
# Start (or restart) the full Docker Compose stack.
#
# Run from anywhere:
#   ./scripts/docker_start.sh              # start without rebuilding images
#   ./scripts/docker_start.sh --build      # rebuild middleware + frontend, then start
#
# The middleware image bakes in backend code (no source mount). After changing
# Python/RAG code, use --build or ./scripts/docker_setup.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/lib/docker_common.sh
source "$ROOT/scripts/lib/docker_common.sh"

DO_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --build) DO_BUILD=1 ;;
    -h|--help)
      echo "Usage: $0 [--build]"
      echo
      echo "  (no args)   docker compose up -d"
      echo "  --build     docker compose up --build -d  (pick up backend/middleware changes)"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

if [[ "$DO_BUILD" -eq 1 ]]; then
  echo "==> Building and starting Docker Compose stack..."
  docker compose up --build -d
else
  echo "==> Starting Docker Compose stack (db, redis, middleware, frontend)..."
  echo "    Tip: changed backend code? Run $0 --build"
  docker compose up -d
fi

echo
echo "==> Waiting for API health..."
HEALTH_OK=0
for _ in $(seq 1 20); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "    OK: http://localhost:8000/health"
    HEALTH_OK=1
    break
  fi
  sleep 2
done
if [[ "$HEALTH_OK" -eq 0 ]]; then
  echo "    WARNING: health check did not pass — try: docker compose logs middleware" >&2
fi

echo
docker compose ps
echo
print_docker_start_footer
echo
