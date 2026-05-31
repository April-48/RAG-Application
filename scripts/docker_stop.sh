#!/usr/bin/env bash
# Stop all Docker Compose services (keeps volumes / data).
#
# Run from anywhere:
#   ./scripts/docker_stop.sh
#
# Wipe DB/Redis/uploads volumes:
#   docker compose down -v

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Stopping Docker Compose stack..."
docker compose down
echo "    Done (volumes preserved). To wipe data: docker compose down -v"
