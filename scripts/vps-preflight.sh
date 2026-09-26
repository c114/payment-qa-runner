#!/usr/bin/env bash
# Ubuntu/Debian VPS preflight — PASS / WARN / FAIL
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PASS=0; WARN=0; FAIL=0

ok()   { echo "PASS  $1${2:+ — $2}"; PASS=$((PASS+1)); }
warn() { echo "WARN  $1${2:+ — $2}"; WARN=$((WARN+1)); }
bad()  { echo "FAIL  $1${2:+ — $2}"; FAIL=$((FAIL+1)); }

# OS
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ok "Operating System" "$PRETTY_NAME" ;;
    *) warn "Operating System" "${PRETTY_NAME:-unknown} (script targets Ubuntu/Debian)" ;;
  esac
else
  warn "Operating System" "unknown"
fi

# Arch
a=$(uname -m)
case "$a" in
  x86_64|amd64|aarch64|arm64) ok "Architecture" "$a" ;;
  *) warn "Architecture" "$a" ;;
esac

# Disk
avail_kb=$(df -Pk "$ROOT" 2>/dev/null | awk 'NR==2{print $4}')
if [[ -n "${avail_kb:-}" && "$avail_kb" -gt 2097152 ]]; then
  ok "Disk Space" "$((avail_kb/1024/1024))GB free"
elif [[ -n "${avail_kb:-}" && "$avail_kb" -gt 1048576 ]]; then
  warn "Disk Space" "$((avail_kb/1024))MB free (<2GB)"
else
  bad "Disk Space" "${avail_kb:-unknown}"
fi

# RAM
if [[ -r /proc/meminfo ]]; then
  mem_kb=$(awk '/MemTotal/{print $2}' /proc/meminfo)
  if [[ "$mem_kb" -ge 2097152 ]]; then ok "RAM" "$((mem_kb/1024))MB"
  elif [[ "$mem_kb" -ge 1048576 ]]; then warn "RAM" "$((mem_kb/1024))MB (recommend ≥2GB)"
  else bad "RAM" "$((mem_kb/1024))MB"
  fi
else
  warn "RAM" "unknown"
fi

port_free() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then ! ss -ltn "sport = :$p" 2>/dev/null | grep -q ":$p"
  elif command -v lsof >/dev/null 2>&1; then ! lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1
  else return 0; fi
}
if port_free 3000; then ok "Port 3000"; else warn "Port 3000" "in use (ok if already installed)"; fi
if port_free 8000; then ok "Port 8000"; else warn "Port 8000" "in use (ok if already installed)"; fi

if getent hosts github.com >/dev/null 2>&1 || ping -c1 -W2 1.1.1.1 >/dev/null 2>&1; then
  ok "DNS"
else
  warn "DNS" "cannot resolve (check network)"
fi

if command -v docker >/dev/null 2>&1; then ok "Docker" "$(docker --version 2>/dev/null | head -1)"
else bad "Docker" "not found — install.sh will install"; fi

if docker compose version >/dev/null 2>&1; then ok "Docker Compose" "$(docker compose version 2>/dev/null | head -1)"
else bad "Docker Compose" "plugin missing"; fi

if [[ -f "$ROOT/.env" ]]; then ok ".env"; else warn ".env" "missing — install.sh creates from .env.example"; fi

mkdir -p "$ROOT/data" "$ROOT/data/screenshots" "$ROOT/data/reports" "$ROOT/data/logs" "$ROOT/backups"
if [[ -w "$ROOT/data" ]]; then ok "Directory Permission" "data/ writable"
else bad "Directory Permission" "data/ not writable"; fi

echo "----"
echo "Result: $PASS PASS, $WARN WARN, $FAIL FAIL"
[[ "$FAIL" -eq 0 ]]
