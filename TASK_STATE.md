# TASK_STATE — Payment Test Runner 2.0.0

## Current phase
Phase 7–8 — Docker/scripts/README + tests + Release (in progress)

## Done
- [x] Audit 1.3.1 keep/delete/rewrite
- [x] TASK_SPEC.md + TASK_STATE.md
- [x] Fresh 2.0 models + Alembic `001_v2_initial` (wiped 1.x migrations)
- [x] Seed admin + Preply Production smoke + Local Sandbox bind + Direct network
- [x] Backend API rewrite (auth/accounts/test-data/tasks/networks/runs/results/artifacts/cleanup/health/readiness)
- [x] Local Sandbox Docker service (`sandbox/main.py`)
- [x] Worker state machine + Preply smoke + sandbox full bind (LIVE only)
- [x] Frontend Shell nav + home/accounts/test-data/runs/tasks/settings; old pages redirect home
- [x] docker-compose (frontend/backend/worker/sandbox), version 2.0.0, README
- [x] Backend pytest 17 passed (incl. Local Sandbox Playwright E2E)
- [x] Frontend lint (warnings only) + build PASS

## Tests
| Test | Status |
|------|--------|
| Backend pytest (17) | PASS |
| Sandbox E2E BOUND/DECLINED/3DS/INVALID/UNKNOWN/DELAYED/bad creds | PASS |
| Import/normalize/dedupe accounts+cards | PASS |
| Run isolation + pairing + stop API | PASS |
| Result codes never unknown→SUCCESS | PASS |
| Network direct probe | PASS |
| Frontend lint + build | PASS |
| Docker compose build + up + health | IN PROGRESS |
| Preply production real login | NOT TESTED (no creds) |
| Restart persistence (compose) | NOT TESTED yet |
| TXT/CSV export via live run | NOT TESTED (API covered) |
| Screenshot/trace cleanup full path | PARTIAL (cleanup API covered) |

## Todo
- [ ] Finish docker compose up + health proof
- [ ] Phase commits + Release 2.0.0 + push origin/main

## Issues
- Frontend hook exhaustive-deps warnings (non-blocking)
- Old 1.x service modules (account_creation, allowlist, etc.) still on disk but unused by 2.0 routes — safe to leave or delete in cleanup commit

## Next Step
Complete docker compose health, commit Release 2.0.0, push origin/main.

## Last Stable Commit
`61eb716` — docs TASK_SPEC/TASK_STATE (more commits pending)

## Notes
UI: Simplified Chinese. User: 文瀚 黄. Mode always LIVE.
