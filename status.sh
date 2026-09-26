#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "==> docker compose ps"
docker compose ps || true
echo
echo "==> /api/health"
if ! curl -sf http://127.0.0.1:8000/api/health -o /tmp/pqa_health.json; then
  echo "FAIL  cannot reach http://127.0.0.1:8000/api/health"
  exit 1
fi
python3 - <<'PY'
import json
d=json.load(open("/tmp/pqa_health.json"))
order=["backend","database","worker","browser_worker"]
for k in order:
    v=d.get(k,{})
    if isinstance(v, dict):
        st=v.get("status","?")
        ls=v.get("last_seen","")
        print(f"{k:16} {st:8} last_seen={ls}")
    else:
        print(f"{k:16} {v}")
PY
