#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Update Payment QA Runner 1.3.1"

BACKUP_OUT=""
if BACKUP_OUT=$(./backup.sh | tee /dev/stderr | awk '/Backup written:/{print $3; exit}'); then
  echo "==> Backup kept at: $BACKUP_OUT"
else
  echo "ERROR: backup failed — aborting update"
  exit 1
fi

# Never delete .env or data/
if [[ ! -f .env ]]; then
  echo "WARN: .env missing — copy from .env.example if needed (will not overwrite data/)"
fi

if [[ -d .git ]]; then
  git fetch origin || true
  # Move conflicting untracked/local changes aside before pull
  TS=$(date +%Y%m%d-%H%M%S)
  CONFLICT_DIR="backups/local-changes-${TS}"
  # Stash tracked local mods if any
  if ! git diff --quiet || ! git diff --cached --quiet; then
    mkdir -p "$CONFLICT_DIR"
    git status --porcelain > "$CONFLICT_DIR/status.txt" || true
    git stash push -u -m "pqa-update-${TS}" || true
    echo "==> Local git changes stashed / noted under $CONFLICT_DIR"
  fi
  # Untracked files that would block checkout
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    status=${line:0:2}
    file=${line:3}
    if [[ "$status" == "??" || "$status" == "A " ]]; then
      case "$file" in
        .env|data|data/*|backups|backups/*) continue ;;
      esac
      mkdir -p "$CONFLICT_DIR/$(dirname "$file")"
      if [[ -e "$file" ]]; then
        cp -a "$file" "$CONFLICT_DIR/$file" 2>/dev/null || true
      fi
    fi
  done < <(git status --porcelain 2>/dev/null || true)

  if ! git pull origin main; then
    echo "git pull failed — backup kept: $BACKUP_OUT"
    echo "Rollback: ./restore.sh $BACKUP_OUT && docker compose up -d"
    exit 1
  fi
fi

# Ensure PLAYWRIGHT_MOCK default stays 0 if unset; never wipe .env secrets
if [[ -f .env ]] && ! grep -q '^PLAYWRIGHT_MOCK=' .env; then
  echo "PLAYWRIGHT_MOCK=0" >> .env
fi
mkdir -p data/sessions
chmod 700 data/sessions 2>/dev/null || true

if ! docker compose build; then
  echo "Build failed — backup kept: $BACKUP_OUT"
  echo "Rollback: ./restore.sh $BACKUP_OUT && docker compose up -d"
  exit 1
fi

docker compose up -d
docker compose exec -T backend alembic upgrade head 2>/dev/null || true
sleep 5

if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  echo "Update OK"
  curl -s http://127.0.0.1:8000/api/health; echo
  echo "Frontend: http://$(hostname -I 2>/dev/null | awk '{print $1}'):3000"
  echo "Backup retained: $BACKUP_OUT"
  echo ".env and data/ were NOT deleted."
else
  echo "Health check failed after update."
  echo "Backup retained (NOT deleted): $BACKUP_OUT"
  echo "Rollback: ./restore.sh $BACKUP_OUT && docker compose up -d"
  exit 1
fi
