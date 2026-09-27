# TASK_STATE — Payment Test Runner 2.0.0

## Current phase
Phase 1 — Fresh schema + Alembic + seed (in progress)

## Done
- [x] Audit 1.3.1 keep/delete/rewrite
- [x] Write TASK_SPEC.md (sections 1–33)
- [x] Write TASK_STATE.md

## Tests
| Test | Status |
|------|--------|
| (none yet) | — |

## Todo
- [ ] Fresh 2.0 DB models + Alembic revision chain
- [ ] Seed admin + Preply + Sandbox tasks + Direct network
- [ ] Backend parsers/services/routes rewrite
- [ ] Sandbox Docker service (Login→Payment→Add Card→Result)
- [ ] Worker state machine + Preply smoke + sandbox full bind
- [ ] Frontend: Shell nav + home + accounts + test-data + runs + tasks + settings
- [ ] Delete old frontend pages from main flow
- [ ] docker-compose + install/update scripts + README → 2.0.0
- [ ] pytest suite + sandbox E2E + frontend build + compose health
- [ ] Phase commits + Release 2.0.0 + push origin/main

## Issues
- None yet. Old 1.x SQLite will be wiped (by design).

## Next Step
Implement fresh models, Alembic 001_v2_initial, bootstrap seed, then backend API skeleton.

## Last Stable Commit
`dcf9502` — Release Payment QA Runner 1.3.1 (baseline before 2.0 rewrite)

## Notes
UI language: Simplified Chinese (bilingual OK). User: 文瀚 黄.
