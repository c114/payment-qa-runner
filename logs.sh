#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
SVC="${1:-}"
if [[ -z "$SVC" ]]; then
  docker compose logs -f --tail=200
else
  case "$SVC" in
    backend|worker|frontend|postgres) docker compose logs -f --tail=200 "$SVC" ;;
    *) echo "Usage: ./logs.sh [backend|worker|frontend]"; exit 1 ;;
  esac
fi
