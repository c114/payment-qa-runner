#!/usr/bin/env bash
# Payment QA Runner — one-click installer (Ubuntu 22.04/24.04, Debian 12/13)
# Public: curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
set -euo pipefail

REPO_SLUG="c114/payment-qa-runner"
INSTALL_DIR="${INSTALL_DIR:-/opt/payment-qa-runner}"
VERSION="1.3.0"

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: run with sudo: sudo bash install.sh"
    exit 1
  fi
}

detect_arch() {
  local a
  a=$(uname -m)
  case "$a" in
    x86_64|amd64) echo "amd64" ;;
    aarch64|arm64) echo "arm64" ;;
    *) echo "$a" ;;
  esac
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "==> Docker already installed"
    return 0
  fi
  echo "==> Installing Docker Engine + Compose plugin (official)"
  apt-get update -y
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker || true
}

gen_hex() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 256; }
gen_fernet() {
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
    || python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
}
gen_password() { openssl rand -base64 24 2>/dev/null | tr -d '/+=' | head -c 24; }

set_env_kv() {
  local key="$1" val="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$file"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

get_env() {
  local key="$1" file="$2"
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true
}

is_weak_admin_pw() {
  local pw="$1"
  [[ -z "$pw" || "$pw" == ChangeMe_* || "$pw" == *example* || "$pw" == *changeme* || "$pw" == *ChangeMe* ]]
}

detect_server_ip() {
  hostname -I 2>/dev/null | awk '{print $1}' || curl -fsS --max-time 3 https://ifconfig.me 2>/dev/null || echo "SERVER_IP"
}

need_root

ARCH=$(detect_arch)
echo "==> Payment QA Runner ${VERSION} installer (arch=${ARCH})"

. /etc/os-release 2>/dev/null || true
echo "==> Distro: ${ID:-unknown} ${VERSION_ID:-}"

apt-get update -y
apt-get install -y curl git ca-certificates openssl python3

install_docker

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CREATED_ADMIN_PW=""

# If already inside a checkout, use it; else clone to INSTALL_DIR
if [[ -f "$SCRIPT_DIR/docker-compose.yml" && -f "$SCRIPT_DIR/.env.example" ]]; then
  ROOT="$SCRIPT_DIR"
  echo "==> Using existing project at $ROOT"
  if [[ -d "$ROOT/.git" ]]; then
    echo "==> Project already present — fetching remotes (not overwriting data/)"
    git -C "$ROOT" fetch --all --prune || true
    echo "TIP: to apply upstream code updates later: cd $ROOT && sudo bash update.sh"
  fi
else
  ROOT="$INSTALL_DIR"
  mkdir -p "$(dirname "$ROOT")"
  if [[ -d "$ROOT/.git" ]]; then
    echo "==> $ROOT already exists — fetch only (use update.sh to upgrade)"
    git -C "$ROOT" fetch --all --prune || true
  else
    echo "==> Cloning https://github.com/${REPO_SLUG} -> $ROOT"
    if git clone "https://github.com/${REPO_SLUG}.git" "$ROOT" 2>/dev/null; then
      :
    elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
      gh repo clone "$REPO_SLUG" "$ROOT"
    else
      echo "ERROR: Could not clone repository."
      echo "  git clone https://github.com/${REPO_SLUG}.git ${INSTALL_DIR}"
      echo "  cd ${INSTALL_DIR} && sudo bash install.sh"
      exit 1
    fi
  fi
fi

cd "$ROOT"

mkdir -p data/screenshots data/reports data/logs data/sessions backups
chmod 700 data/sessions 2>/dev/null || true
chmod 755 data data/screenshots data/reports data/logs backups

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
fi

# Secrets
jwt=$(get_env JWT_SECRET .env)
if [[ -z "$jwt" || "$jwt" == *change-me* ]]; then
  set_env_kv JWT_SECRET "$(gen_hex)" .env
  echo "==> Generated JWT_SECRET"
fi
sess=$(get_env SESSION_SECRET .env)
if [[ -z "$sess" || "$sess" == *change-me* ]]; then
  set_env_kv SESSION_SECRET "$(gen_hex)" .env
  echo "==> Generated SESSION_SECRET"
fi
enc=$(get_env ENCRYPTION_KEY .env)
if [[ -z "$enc" ]]; then
  set_env_kv ENCRYPTION_KEY "$(gen_fernet)" .env
  echo "==> Generated ENCRYPTION_KEY"
fi

admin_pw=$(get_env ADMIN_PASSWORD .env)
if is_weak_admin_pw "$admin_pw"; then
  CREATED_ADMIN_PW="$(gen_password)"
  set_env_kv ADMIN_PASSWORD "$CREATED_ADMIN_PW" .env
  echo "==> Generated temporary ADMIN_PASSWORD (shown once at end)"
fi

# Safe defaults — Same-Origin: no NEXT_PUBLIC_API_URL / public CORS IP required
set_env_kv PLAYWRIGHT_MOCK "0" .env
set_env_kv LIVE_TESTING_ENABLED "false" .env
set_env_kv CORS_ORIGINS "http://localhost:3000,http://127.0.0.1:3000" .env
# Remove any baked NEXT_PUBLIC_API_URL so browser uses same-origin /api
if grep -q '^NEXT_PUBLIC_API_URL=' .env 2>/dev/null; then
  set_env_kv NEXT_PUBLIC_API_URL "" .env
fi

chmod 600 .env
rm -f .env.bak 2>/dev/null || true

echo "==> docker compose config"
docker compose config >/dev/null

echo "==> docker compose build"
docker compose build

echo "==> docker compose up -d"
docker compose up -d

echo "==> Waiting for health"
HEALTH="FAIL"
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    HEALTH="PASS"
    break
  fi
  sleep 2
done

# Also check frontend Same-Origin proxy
FRONT_HEALTH="FAIL"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:3000/ >/dev/null 2>&1; then
    FRONT_HEALTH="PASS"
    break
  fi
  sleep 2
done

if [[ "$HEALTH" != "PASS" ]]; then
  echo "ERROR: backend health check failed"
  docker compose ps || true
  docker compose logs --tail=200 || true
  exit 1
fi

SERVER_IP=$(detect_server_ip)
ADMIN_EMAIL=$(get_env ADMIN_EMAIL .env)
REPO_URL="https://github.com/${REPO_SLUG}"

echo
echo "========================================"
echo "Payment QA Runner Installed Successfully"
echo "========================================"
echo
echo "Repository:"
echo "$REPO_URL"
echo
echo "Version:"
echo "$VERSION"
echo
echo "Install Directory:"
echo "$ROOT"
echo
echo "Admin URL (Same-Origin API via /api):"
echo "http://${SERVER_IP}:3000"
echo
echo "API (debug / health scripts):"
echo "http://${SERVER_IP}:8000"
echo
echo "Admin Email:"
echo "${ADMIN_EMAIL}"
echo
if [[ -n "$CREATED_ADMIN_PW" ]]; then
  echo "Temporary Admin Password:"
  echo "$CREATED_ADMIN_PW"
  echo "(change this after first login — not stored in git/logs)"
  echo
fi
echo "Backend Health: $HEALTH"
echo "Frontend Health: $FRONT_HEALTH"
echo
echo "Status:"
echo "docker compose ps"
docker compose ps || true
echo
echo "Update:"
echo "cd $ROOT && sudo bash update.sh"
echo
echo "Diagnose:"
echo "cd $ROOT && sudo bash diagnose.sh"
echo
echo "========================================"
