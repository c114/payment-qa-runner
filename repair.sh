#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Repair Payment QA Runner"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "==> Docker missing — attempting install (requires root)"
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: run with sudo to install Docker"
    exit 1
  fi
  bash install.sh || true
fi

echo "==> Ensuring directories"
mkdir -p data/screenshots data/reports data/logs backups docs/screenshots
chmod 755 data data/screenshots data/reports data/logs backups || true

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Restored .env from example — re-run install.sh to regenerate secrets"
fi

# Ensure DB parent exists for sqlite path
if grep -q 'sqlite:////data/' .env 2>/dev/null; then
  mkdir -p data
fi

echo "==> Restarting services"
docker compose up -d --remove-orphans || docker compose up -d
sleep 3
curl -sf http://127.0.0.1:8000/api/health && echo || echo "WARN: health still failing — see diagnose.sh"
docker compose ps || true
echo "==> Repair done"
