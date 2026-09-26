# ACCEPTANCE — Payment QA Runner

Generated: 2026-09-26 (Asia/Shanghai)

## Directory tree (source, truncated)

```
./.env.example
./.gitignore
./README.md
./backend/.pytest_cache/.gitignore
./backend/.pytest_cache/CACHEDIR.TAG
./backend/.pytest_cache/README.md
./backend/.pytest_cache/v/cache/lastfailed
./backend/.pytest_cache/v/cache/nodeids
./backend/.pytest_cache/v/cache/stepwise
./backend/Dockerfile
./backend/alembic.ini
./backend/alembic/env.py
./backend/alembic/script.py.mako
./backend/alembic/versions/001_initial.py
./backend/app/__init__.py
./backend/app/api/__init__.py
./backend/app/api/deps.py
./backend/app/api/routes.py
./backend/app/core/__init__.py
./backend/app/core/config.py
./backend/app/core/database.py
./backend/app/core/security.py
./backend/app/main.py
./backend/app/models/__init__.py
./backend/app/models/models.py
./backend/app/schemas/__init__.py
./backend/app/schemas/schemas.py
./backend/app/seed/__init__.py
./backend/app/seed/bootstrap.py
./backend/app/services/__init__.py
./backend/app/services/account_creation.py
./backend/app/services/allowlist.py
./backend/app/services/comparison.py
./backend/app/services/help_content.py
./backend/app/services/parsers.py
./backend/app/services/selector_test.py
./backend/requirements.txt
./backend/tests/__init__.py
./backend/tests/test_account_creation.py
./backend/tests/test_allowlist.py
./backend/tests/test_comparison.py
./backend/tests/test_db_smoke.py
./backend/tests/test_mock_workflow.py
./backend/tests/test_parsers.py
./backend/tests/test_security.py
./backup.sh
./deploy.sh
./docker-compose.yml
./docs/screenshots/page-1.png
./docs/screenshots/page-2.png
./docs/screenshots/page-3.png
./docs/screenshots/page-4.png
./docs/screenshots/page-5.png
./docs/screenshots/page-6.png
./docs/screenshots/page-7.png
./examples/qa_accounts.txt
./examples/socks5.txt
./examples/test_cases.txt
./frontend/.eslintrc.json
./frontend/Dockerfile
./frontend/app/accounts/page.tsx
./frontend/app/cases/page.tsx
./frontend/app/environments/page.tsx
./frontend/app/globals.css
./frontend/app/help/page.tsx
./frontend/app/import/page.tsx
./frontend/app/layout.tsx
./frontend/app/login/page.tsx
./frontend/app/logs/page.tsx
./frontend/app/page-mapping/page.tsx
./frontend/app/page.tsx
./frontend/app/proxies/page.tsx
./frontend/app/reports/page.tsx
./frontend/app/results/page.tsx
./frontend/app/runs/page.tsx
./frontend/app/screenshots/page.tsx
./frontend/app/sessions/page.tsx
./frontend/app/settings/page.tsx
./frontend/components/Shell.tsx
./frontend/lib/api.ts
./frontend/lib/i18n.ts
./frontend/next-env.d.ts
./frontend/next.config.mjs
./frontend/package-lock.json
./frontend/package.json
./frontend/postcss.config.mjs
./frontend/public/robots.txt
./frontend/tailwind.config.ts
./frontend/tsconfig.json
./restore.sh
./update.sh
./worker/Dockerfile
./worker/__init__.py
./worker/requirements.txt
./worker/runner.py
```

## Implemented vs not

### Implemented
- Backend: Auth JWT, Dashboard+wizard 1–11, Environments(+Test HTTP), Page Mapping(+Test Selector mock/live hook), Workflow Steps, QA Accounts(+TXT import, test-login decrypt check, encrypted password), Account creation settings (OFF, domain blocklist), SOCKS5(+TXT, Test TCP latency/status, encrypted password), Network Profiles (Direct seeded), Browser Sessions(+all actions; switch_network → new context flag), Test Cases(+flexible TXT import, no CVV), Test Runs(create/START/PAUSE/RESUME/STOP, counts 1|5|10|50|ALL), Runner settings (decline_retry forced 0), Results+timeline, Screenshots list, Reports CSV/XLSX/JSON/HTML, System Settings, Payrails panel (blank secrets), Logs redacted, Health backend+db+worker, Help endpoints
- Worker: DB poll queue, allowlist, mock mode, live Playwright path, 3DS abort, Expected vs Actual, network-switch policy, account cooldown, screenshots policy hooks
- Frontend: all listed pages, zh default + en toggle, dark UI, help button
- Dockerfiles + docker-compose (+ postgres profile), deploy/update/backup/restore, .env.example, examples/, seed data, Alembic baseline
- Tests: parsers, comparison/3DS, allowlist, redaction, encryption, account-creation policy, mock workflow, DB seed smoke; frontend `next build`

### Not / limited
- Live Payrails payment against a real sandbox was **not** executed in this environment (no admin-provided sandbox URL/secrets). Use mock or configure Payrails panel.
- Selector Test live path requires Playwright in API process; mock returns success when `PLAYWRIGHT_MOCK=1`.
- SOCKS5 “exit IP” probe is best-effort (TCP connect → ONLINE); full SOCKS handshake/IP check can be extended.
- Browser Sessions do not keep a long-lived headed browser UI; actions are queued/acknowledged for worker.
- **Docker was not available** on the build host (`docker: command not found`), so `docker compose up` was **not** run here. Compose files are present for VPS use.
- Next.js 14.2.21 npm audit reports a known advisory; bump Next when deploying to production.

## Commands run

```bash
# Unit tests
cd backend && pytest tests/ -v
# → 21 passed

# Frontend
cd frontend && npm install && npm run build
# → success (19 routes)

# Local integration (mock)
uvicorn + worker with PLAYWRIGHT_MOCK=1
curl /api/health → backend+db+worker true
import examples/test_cases.txt → 7 cases
create run ALL → worker COMPLETED 6 PASS / 1 FAIL
  (TC006 SUCCESS vs 3DS = FAIL; TC007 3DS vs 3DS = PASS)

# Docker
docker compose config / up  → SKIPPED (docker not installed)
```

## Pytest result (excerpt)

```
tests/test_allowlist.py::test_empty_allowlist_fail_closed PASSED         [ 19%]
tests/test_allowlist.py::test_assert_raises PASSED                       [ 23%]
tests/test_allowlist.py::test_extract_host PASSED                        [ 28%]
tests/test_comparison.py::test_declined_vs_declined_pass PASSED          [ 33%]
tests/test_comparison.py::test_success_vs_declined_fail PASSED           [ 38%]
tests/test_comparison.py::test_threeds_fails_unless_expected PASSED      [ 42%]
tests/test_comparison.py::test_network_switch_policy PASSED              [ 47%]
tests/test_db_smoke.py::test_create_all_and_seed PASSED                  [ 52%]
tests/test_mock_workflow.py::test_mock_workflow_pass_and_threeds PASSED  [ 57%]
tests/test_mock_workflow.py::test_mock_blocks_outside_allowlist PASSED   [ 61%]
tests/test_parsers.py::test_parse_qa_accounts PASSED                     [ 66%]
tests/test_parsers.py::test_parse_socks5 PASSED                          [ 71%]
tests/test_parsers.py::test_parse_test_cases_no_cvv PASSED               [ 76%]
tests/test_security.py::test_encryption_roundtrip PASSED                 [ 80%]
tests/test_security.py::test_mask_pan PASSED                             [ 85%]
tests/test_security.py::test_redaction PASSED                            [ 90%]
tests/test_security.py::test_never_persist_cvv PASSED                    [ 95%]
tests/test_security.py::test_password_hash PASSED                        [100%]

=============================== warnings summary ===============================
app/models/models.py:138
  /workspace/payment-qa-runner/backend/app/models/models.py:138: PytestCollectionWarning: cannot collect test class 'TestCase' because it has a __init__ constructor (from: tests/test_mock_workflow.py)
    class TestCase(Base):

tests/test_mock_workflow.py::test_mock_workflow_pass_and_threeds
  /workspace/payment-qa-runner/backend/tests/test_mock_workflow.py:36: DeprecationWarning: There is no current event loop
    r1 = asyncio.get_event_loop().run_until_complete(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 21 passed, 2 warnings in 1.25s ========================
```

## Next build (excerpt)

```
 ✓ Compiled successfully
   Generating static pages (0/19) ...
   Generating static pages (4/19) 
   Generating static pages (9/19) 
   Generating static pages (14/19) 
 ✓ Generating static pages (19/19)
Route (app)                              Size     First Load JS
```

## Env field docs

| Variable | Purpose |
|----------|---------|
| ADMIN_EMAIL / ADMIN_PASSWORD | First-boot admin |
| JWT_SECRET | JWT signing |
| ENCRYPTION_KEY | Fernet key for QA/proxy/Payrails secrets (auto-derived from JWT if empty — set in prod) |
| DATABASE_URL | sqlite:////data/payment_qa.db or PostgreSQL URL |
| CORS_ORIGINS | Frontend origins |
| PLAYWRIGHT_MOCK | 1 = no real browser payment |
| WORKER_POLL_INTERVAL_SEC | Queue poll |
| MAX_CONCURRENT_BROWSERS | Default 1 |
| SCREENSHOT_DIR / REPORT_DIR / LOG_DIR | Runtime paths |
| NEXT_PUBLIC_API_URL | Frontend → API |

## Integration smoke results

| Case | Expected | Actual | Status |
|------|----------|--------|--------|
| TC001 | SUCCESS | SUCCESS | PASS |
| TC002 | DECLINED | DECLINED | PASS |
| TC003 | INVALID_CARD | INVALID_CARD | PASS |
| TC004 | INVALID_CVV | INVALID_CVV | PASS |
| TC005 | INSUFFICIENT_FUNDS | INSUFFICIENT_FUNDS | PASS |
| TC006 | SUCCESS | 3DS | FAIL |
| TC007 | 3DS | 3DS | PASS |

## Panel-only ops guide

1. Login → Environments：创建沙箱 URL + allowed_domains → Test  
2. Page Mapping：按截图改选择器 → Test Selector  
3. Accounts / Proxies：手工或 TXT 导入 → Test  
4. Settings：Runner + Payrails（填真实沙箱，勿造密钥）  
5. Cases：导入 examples/test_cases.txt  
6. Runs：创建 → START；Dashboard 可 PAUSE/RESUME/STOP  
7. Results / Reports 导出；Logs 已脱敏  

## Known limits

- Mock 根据 `payment_test_ref` 启发式出结果，不等于真实 Payrails。  
- 正式站支付默认禁用；preply.com 仅 UI 参考。  
- Docker 需在目标 VPS 执行 `./deploy.sh`。  

## Docker compose succeeded?

**NO** — Docker CLI not installed on this host. Images/compose/scripts are ready for deployment elsewhere.
