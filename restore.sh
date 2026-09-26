#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Usage: ./restore.sh backups/pqa_backup_YYYYMMDD_HHMMSS.tgz"
  exit 1
fi
echo "==> Restoring from $FILE"
tar xzf "$FILE" -C "$ROOT"
echo "Restore done. Restart: docker compose up -d"
