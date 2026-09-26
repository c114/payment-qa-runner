#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Payment QA Runner deploy"

STRICT_PRODUCTION="${STRICT_PRODUCTION:-0}"
RUN_PREFLIGHT="${RUN_PREFLIGHT:-1}"

if [[ "$RUN_PREFLIGHT" == "1" && -x scripts/vps-preflight.sh ]]; then
  echo "==> Preflight"
  # Preflight may FAIL on secrets before we generate them — run after .env prep for secrets
  :
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found"; exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose not found"; exit 1
fi

if [[ ! -f .env ]]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
fi

# Strong random generators
gen_hex() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 256; }
gen_fernet() {
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
    || python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null \
    || gen_hex
}

set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

# Generate SESSION_SECRET / JWT_SECRET / ENCRYPTION_KEY if missing or placeholder
if ! grep -q '^JWT_SECRET=.\+' .env || grep -qE 'JWT_SECRET=(change-me|dev-jwt)' .env; then
  set_env JWT_SECRET "$(gen_hex)"
  echo "==> Generated JWT_SECRET"
fi
if ! grep -q '^SESSION_SECRET=.\+' .env || grep -qE 'SESSION_SECRET=(change-me|$)' .env; then
  set_env SESSION_SECRET "$(gen_hex)"
  echo "==> Generated SESSION_SECRET"
fi
if ! grep -q '^ENCRYPTION_KEY=.\+' .env || grep -qE '^ENCRYPTION_KEY=\s*$' .env; then
  set_env ENCRYPTION_KEY "$(gen_fernet)"
  echo "==> Generated ENCRYPTION_KEY"
fi

# Default safe flags if missing
grep -q '^PLAYWRIGHT_MOCK=' .env || echo "PLAYWRIGHT_MOCK=1" >> .env
grep -q '^LIVE_TESTING_ENABLED=' .env || echo "LIVE_TESTING_ENABLED=false" >> .env

ADMIN_PW=$(grep -E '^ADMIN_PASSWORD=' .env | head -1 | cut -d= -f2- || true)
if [[ "$ADMIN_PW" == "ChangeMe_Admin_123!" || "$ADMIN_PW" == ChangeMe_* ]]; then
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "WARNING: ADMIN_PASSWORD is still the example ChangeMe_* value."
  echo "Change it before exposing this host to the internet."
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  if [[ "$STRICT_PRODUCTION" == "1" ]]; then
    echo "ERROR: STRICT_PRODUCTION=1 — refusing to deploy with example admin password"
    exit 1
  fi
fi

mkdir -p data/screenshots data/reports data/logs

if [[ "$RUN_PREFLIGHT" == "1" && -x scripts/vps-preflight.sh ]]; then
  scripts/vps-preflight.sh || {
    echo "WARN: preflight reported FAIL lines — review above"
    if [[ "$STRICT_PRODUCTION" == "1" ]]; then
      echo "ERROR: STRICT_PRODUCTION=1 and preflight failed"
      exit 1
    fi
  }
fi

echo "==> Building and starting"
docker compose up -d --build

echo "==> Waiting for health"
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null; then
    echo "Health OK"
    curl -s http://localhost:8000/api/health
    echo
    echo "Frontend: http://localhost:3000"
    echo "API docs: http://localhost:8000/docs"
    echo "With domain: see deploy/Caddyfile.example"
    echo "Logs: docker compose logs -f"
    exit 0
  fi
  sleep 2
done
echo "WARN: health not ready yet; check: docker compose logs"
exit 1
