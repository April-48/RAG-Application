#!/usr/bin/env bash
# Helpers for switching DATABASE_URL / REDIS_URL between Docker and host dev.

set_env_for_host() {
  local env_file="${1:-.env}"
  [[ -f "$env_file" ]] || return 0
  if grep -q '@db:5432' "$env_file" 2>/dev/null; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      sed -i '' 's|@db:5432|@localhost:5432|g' "$env_file"
      sed -i '' 's|redis://redis:|redis://localhost:|g' "$env_file"
    else
      sed -i 's|@db:5432|@localhost:5432|g' "$env_file"
      sed -i 's|redis://redis:|redis://localhost:|g' "$env_file"
    fi
    echo "    Set DATABASE_URL / REDIS_URL to localhost (host dev)"
  fi
}

set_env_for_docker() {
  local env_file="${1:-.env}"
  [[ -f "$env_file" ]] || return 0
  if grep -q '@localhost:5432' "$env_file" 2>/dev/null; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      sed -i '' 's|@localhost:5432|@db:5432|g' "$env_file"
      sed -i '' 's|redis://localhost:|redis://redis:|g' "$env_file"
    else
      sed -i 's|@localhost:5432|@db:5432|g' "$env_file"
      sed -i 's|redis://localhost:|redis://redis:|g' "$env_file"
    fi
    echo "    Set DATABASE_URL / REDIS_URL to db/redis (Docker Compose)"
  fi
}
