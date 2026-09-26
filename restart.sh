#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "==> docker compose restart"
docker compose restart
echo "==> Waiting for health"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
    echo "Health OK"
    curl -s http://127.0.0.1:8000/api/health; echo
    exit 0
  fi
  sleep 2
done
echo "Health check failed"
docker compose ps || true
exit 1
