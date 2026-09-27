# TASK_STATE — Payment Test Runner 2.0.0

## Current phase
**COMPLETE (gap-fix patch)** — stay on version 2.0.0; installable + Fill+Submit verified.

## Done (this patch)
- Fixed `finish_item`: business FAIL → `status=FAIL` `state=COMPLETED` (not ERROR)
- `adapter_type` on tasks (`preply_ui` | `standard_sandbox_binding`); worker routes by it; seed + Task UI help
- `run_items.final_url` + richer run detail (screenshot/trace/log links, duration)
- docker-compose: backend `127.0.0.1:8000`; sandbox `127.0.0.1:8080` + `172.17.0.1:8080` (host-gateway); no postgres
- install.sh summary: Web UI `SERVER_IP:3000`, local API `127.0.0.1:8000`
- Delete Run FK order fixed (artifacts → items → run)

## Tests (honest)
| Check | Result |
|-------|--------|
| finish_item FAIL→COMPLETED | PASS (pytest) |
| sandbox Chromium BOUND/DECLINED/3DS/INVALID/DELAYED + FILLING/SUBMITTING | PASS (pytest + live API) |
| health version=2.0.0 mode=LIVE | PASS |
| Account/TestData import+dedup, TXT/CSV export | PASS |
| Delete Run (artifacts gone, accounts kept) | PASS |
| Restart persistence | PASS |
| Full `sudo bash install.sh` from empty VPS | NOT TESTED (simulated compose from clean dir; Docker already present) |
| Preply production real login | NOT TESTED (no creds) |

## Issues / Known Limitations
- This host’s Docker bridge blocks container↔container TCP to `sandbox:8080`. Mitigated by `sandbox:host-gateway` + publish on `127.0.0.1` and `172.17.0.1` (not `0.0.0.0`).
- Pure compose DNS without host-gateway **does not work** on this host (proven by timeout).

## Next Step
Operate: `sudo bash install.sh` / open `http://SERVER:3000`

## Last Stable Commit
`f444cef` — fix(2.0.0): finish_item FAIL→COMPLETED, adapter_type, compose binds
