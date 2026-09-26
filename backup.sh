#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p backups data
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="backups/pqa_backup_${STAMP}.tgz"
# Single tarball: data/ + .env.example + .env (if present). Avoid broken `tar rzf` append.
INCLUDE=(data .env.example)
[[ -f .env ]] && INCLUDE+=(.env)
tar czf "$OUT" "${INCLUDE[@]}"
echo "Backup written: $OUT"
echo "$OUT"
