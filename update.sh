#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Update Payment QA Runner"

BACKUP_OUT=""
if BACKUP_OUT=$(./backup.sh | tee /dev/stderr | awk '/Backup written:/{print $3; exit}'); then
  echo "==> Backup kept at: $BACKUP_OUT"
else
  echo "ERROR: backup failed — aborting update"
  exit 1
fi

if [[ -d .git ]]; then
  git fetch origin || true
  git pull origin main || { echo "git pull failed — backup kept: $BACKUP_OUT"; exit 1; }
fi

if ! docker compose build; then
  echo "Build failed — backup kept: $BACKUP_OUT"
  echo "Rollback: ./restore.sh $BACKUP_OUT && docker compose up -d"
  exit 1
fi

docker compose up -d
# Alembic / schema: backend creates on start; optional migrate
docker compose exec -T backend alembic upgrade head 2>/dev/null || true
sleep 3

if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  echo "Update OK"
  curl -s http://127.0.0.1:8000/api/health; echo
  echo "Backup retained: $BACKUP_OUT"
else
  echo "Health check failed after update."
  echo "Backup retained (NOT deleted): $BACKUP_OUT"
  echo "Rollback: ./restore.sh $BACKUP_OUT && docker compose up -d"
  exit 1
fi
