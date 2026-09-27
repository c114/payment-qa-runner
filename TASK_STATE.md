# TASK_STATE — Payment Test Runner 2.0.0

## Current phase
Release 2.0.0 — complete (pending push)

## Done
- [x] TASK_SPEC + TASK_STATE
- [x] Fresh 2.0 schema + Alembic 001_v2_initial
- [x] Seed admin + Preply smoke + Local Sandbox bind + Direct
- [x] Backend API rewrite; delete dead 1.x routes/services/tests
- [x] Sandbox Docker service + Playwright full bind path
- [x] Worker state machine (LIVE only, no Mock PASS)
- [x] Frontend nav + pages; old pages redirect
- [x] docker-compose / install / update / README → 2.0.0
- [x] Backend pytest 17 PASS
- [x] Frontend lint + build PASS
- [x] Docker compose build + up + health PASS
- [x] Live compose E2E: BOUND/DECLINED/3DS/INVALID_DATA PASS

## Tests
| Test | Status |
|------|--------|
| Backend pytest (17) | PASS |
| Sandbox Playwright E2E (pytest embedded) | PASS |
| Live compose E2E BOUND/DECLINED/3DS/INVALID | PASS |
| Import/dedupe accounts+cards | PASS |
| Run isolation + stop API | PASS |
| Network Direct test | PASS |
| Frontend build | PASS |
| Docker compose health | PASS |
| Preply production real login | NOT TESTED (no creds) |
| Delayed redirect (compose) | NOT TESTED (pytest covered) |
| STOP mid-run live | NOT TESTED (API covered) |
| Restart persistence | NOT TESTED |

## Todo
- [ ] Push origin/main

## Issues
- Docker bridge blocked sandbox:8080 inter-container TCP on this host; workaround: publish 8080 + `extra_hosts: sandbox:host-gateway` for backend/worker
- Frontend hook exhaustive-deps warnings (non-blocking)

## Next Step
Push Release 2.0.0 to origin/main.

## Last Stable Commit
(see git log — Release commit pending)

## Notes
Mode always LIVE. UI zh-CN. User: 文瀚 黄.
