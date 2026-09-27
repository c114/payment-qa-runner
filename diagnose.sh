#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "======== Payment QA Runner Diagnose ========"
echo "Version:     1.3.0"
if [[ -d .git ]]; then
  echo "Git commit:  $(git rev-parse --short HEAD 2>/dev/null || echo n/a) ($(git log -1 --format=%s 2>/dev/null || true))"
  echo "Git remote:  $(git remote get-url origin 2>/dev/null || echo n/a)"
fi
echo "OS:          $(uname -srm) · $(. /etc/os-release 2>/dev/null; echo ${PRETTY_NAME:-unknown})"
echo "Date:        $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo
echo "---- Docker ----"
if command -v docker >/dev/null 2>&1; then
  docker --version || true
  docker compose version || true
else
  echo "Docker: NOT INSTALLED"
fi
echo
echo "---- Containers ----"
docker compose ps 2>/dev/null || echo "(compose unavailable)"
echo
echo "---- Health ----"
curl -sf http://127.0.0.1:8000/api/health && echo || echo "backend health: FAIL"
curl -sf -o /dev/null -w "frontend / : %{http_code}\n" http://127.0.0.1:3000/ || echo "frontend: FAIL"
curl -sf -o /dev/null -w "same-origin /api/health : %{http_code}\n" http://127.0.0.1:3000/api/health || echo "proxy /api/health: FAIL"
echo
echo "---- Disk ----"
df -h "$ROOT" 2>/dev/null | tail -1 || df -h . | tail -1
du -sh data backups 2>/dev/null || true
echo
echo "---- Memory ----"
free -h 2>/dev/null || true
echo
echo "---- Recent Logs (tail 40) ----"
docker compose logs --tail=40 2>/dev/null || true
echo "============================================"
