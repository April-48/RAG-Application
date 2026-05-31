#!/usr/bin/env bash
# Shared output helpers for Docker Compose scripts.

print_docker_urls() {
  echo "  Frontend:  http://localhost:5173"
  echo "  API docs:  http://localhost:8000/docs"
  echo "  Health:    http://localhost:8000/health"
}

print_docker_rag_log_tip() {
  echo "  RAG logs:  docker compose logs -f middleware | grep -E 'Retrieval|LLM prompt|Answer path'"
}

print_docker_start_footer() {
  print_docker_urls
  echo
  print_docker_rag_log_tip
  echo "  Stop:      ./scripts/docker_stop.sh"
  echo "  Restart:   ./scripts/docker_start.sh"
  echo "  Rebuild:   ./scripts/docker_start.sh --build   # after backend/middleware code changes"
}

print_docker_setup_footer() {
  print_docker_urls
  echo
  echo "  Logs:      docker compose logs -f middleware"
  print_docker_rag_log_tip
  echo "  Stop:      ./scripts/docker_stop.sh"
  echo "  Restart:   ./scripts/docker_start.sh"
  echo "  Rebuild:   ./scripts/docker_start.sh --build"
}
