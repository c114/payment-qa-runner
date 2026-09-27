# Payment Test Runner 2.0.0 — Product & Tech Spec

> Condensed from user requirements. NOT a generic QA platform / workflow builder / page mapper / case manager.

---

## 1. Product identity

**Payment Test Runner** — 导入账号 → 导入测试数据 → 选账号/任务/网络 → START → 真实 Chromium → SUCCESS/FAIL/ERROR → 导出/清理。

Version **2.0.0**. Mode always **LIVE**. No Live→Mock fallback. Old VPS wiped — **no 1.x SQLite compatibility**. Fresh schema.

## 2. Primary navigation (ONLY)

首页 | 账号 | 测试数据 | 运行记录 | 任务 | 设置

## 3. DELETE from main flow

Environment pages, Page Mapping, Workflow editor, Cases manager, complex Browser Sessions, complex Selector config, old Dashboard QA checklist, Mock-oriented features, Proxies as separate complex page (fold into Network on Home/Settings).

## 4. Keep / reuse

FastAPI, Next.js, Playwright, Docker Compose, install/update script framework, Screenshot/Trace basics, Fernet encryption, JWT auth, account import parsers (normalize).

## 5. Architecture

| Layer | Tech |
|-------|------|
| Frontend | Next.js (App Router) |
| Backend | FastAPI |
| Worker | Playwright Python |
| DB | SQLite + Alembic (fresh 2.0 chain) |
| Compose | frontend, backend, worker, **sandbox** |
| No | Redis, Kafka, microservices |

## 6. DB tables (2.0)

`admins`, `accounts`, `test_data`, `tasks`, `network_profiles`, `sessions`, `runs`, `run_items`, `artifacts`, `settings`

`tasks.adapter_type`: `preply_ui` | `standard_sandbox_binding` — Worker routes by adapter (not URL guessing). URL only works if page structure matches Adapter; different structure needs a new Adapter. No Workflow/Selector UI.
`run_items.final_url`: last page URL after execution.

## 7. API (minimum)

- Auth: login, me
- Accounts: list, import-preview, import-confirm, delete, export, session-clear, select
- Test Data: list, import-preview, import-confirm, delete, export-safe, select
- Tasks: list, create, update, enable, disable, test-url
- Networks: list, create, update, delete, test
- Runs: create, stop, status, details, list
- Results: list, export (TXT/CSV), delete
- Artifacts: screenshot, trace, logs
- Cleanup: preview, execute
- Health: backend/db/worker/chromium/network/disk
- Home readiness: checklist payload

## 8. Home page

Top: Payment Test Runner / Version 2.0.0 / Mode LIVE  
Health: Backend, Database, Worker, Chromium, Network, Disk  
① Accounts: imported/selected + [导入账号][选择账号]  
② Test data: imported/available/selected + [导入测试数据]  
③ Task dropdown: name, target URL, short description  
④ Network: default Direct + HTTP/SOCKS5 profiles  
⑤ Ready checklist ✓/×  
[START] disabled until all required ready; Chinese reasons.

## 9. Pairing rule

1 account ↔ 1 test data. `max_executable = min(selected_accounts, selected_test_data)`. Never reuse same test data in same run. Preply Production smoke may run without test data (login+nav only).

## 10. Accounts

Paste / TXT / CSV. Formats: `email|password`, `email----password`.  
Normalize: trim, ignore blank, trim around separators, unify, detect dupes/errors.  
Preview before write: total/valid/dupe/error + line# + raw + reason. Confirm then. Dupes not re-saved by default.  
List: Email, Status, Session (NONE/VALID/EXPIRED), Last result, Created — **NEVER password**.  
Session: auto reuse VALID; EXPIRED → re-login; user [清除 Session][重新登录]. Passwords Fernet-encrypted.

## 11. Test data (first-class)

Same import UX. Card mask `**** **** **** 4242`. CVC never in list/logs/exports.  
Only for Sandbox/QA/Staging/Internal tasks (**never production card submit**).  
Totals: total/valid/dupe/error/used/unused.

Formats: `number|MM/YY|CVC` or CSV with headers; brand optional.

## 12. Tasks

CRUD: Name, Description, Environment Type (Production|Sandbox|QA|Staging|Internal), Base URL, Login URL, Target URL, Status (enabled/disabled), allow_card_fill derived from env type.  
Every field documents 用途/格式/示例/是否必填 in Chinese.  
[测试地址][保存]. No fallback to another task. Missing required → START disabled.

## 13. Built-in Preply Task (Production)

- Base: https://preply.com  
- Login: https://preply.com/login (or detect redirect)  
- Target: https://preply.com/en/settings/payments  
- Logic: open payment URL; if logged in → Payment methods; if redirected to login → fill email/password; return to payments; detect Payment methods / Add card; may open Add card and detect "Save a payment card".  
- **Production: login + navigation + UI verification ONLY. NO real card fill/submit.**

## 14. Full Card Binding (Sandbox/QA/Staging/Internal ONLY)

Login → Target → Add Card → wait form → Fill number/expiry/CVC → Submit → Wait → Parse result.  
NOT success on merely opening form. Must FILL+SUBMIT+WAIT+PARSE.

## 15. Built-in Local Sandbox (HARD REQUIREMENT)

Docker service `sandbox`:
- Base http://sandbox:8080  
- Login /login  
- Payment /settings/payments  
Pages: Login, Payment Methods, Add Card, Card Form, Submit, Result.  
Simulate: BOUND, DECLINED, 3DS_REQUIRED, INVALID_DATA, DELAYED_REDIRECT, TIMEOUT.  
Seed Task with Environment Type Sandbox. Real Playwright full path against it.

## 16. Result codes

| Code | Meaning |
|------|---------|
| SUCCESS/BOUND | Card bound / smoke OK |
| FAIL/DECLINED | Declined |
| FAIL/3DS_REQUIRED | 3DS challenge — stop item, continue next |
| FAIL/INVALID_DATA | Invalid card data |
| ERROR/BAD_CREDENTIALS | Login failed |
| ERROR/LOGIN_TIMEOUT | Login timeout |
| ERROR/NETWORK_ERROR | Network |
| ERROR/TARGET_NOT_FOUND | Target page missing |
| ERROR/BROWSER_ERROR | Browser crash |
| ERROR/UNKNOWN_RESULT | Unknown — NEVER map to SUCCESS |

## 17. State machine

QUEUED → STARTING_BROWSER → NAVIGATING → WAITING_PAGE → AUTH_REQUIRED → AUTHENTICATING → AUTH_SUCCESS → TARGET_LOADING → TARGET_READY → FORM_OPEN → FILLING → SUBMITTING → WAITING_RESULT → COMPLETED | ERROR | CANCELLED

Poll stable page after goto (10–15s). Treat "Execution context was destroyed because of navigation" as transient. Only timeout → ERROR. No mid-nav screenshots (white-screen fix).

## 18. Live run UI

Run #N: Task, Target, Network, Started At; progress; current account; current step; counts SUCCESS/FAIL/ERROR/RUNNING/WAITING/CANCELLED; live log; [STOP].  
STOP: keep completed; safely stop current; CANCELLED remaining; close Chromium; finish trace; save log. Do NOT kill worker process.

## 19. Run isolation

Each START = new Run. All accounts/test data/task snapshot/network/results/logs/screenshots/traces bound to that Run.

## 20. Results page

Account | Test Data (masked) | Result | Reason + search + filters + Export TXT/CSV + Delete selected + Delete this Run.

## 21. Settings → 数据管理

Counts + disk for accounts/test data/runs/results/screenshots/traces/logs/sessions. Cleanup with confirm. Delete Run deletes results/artifacts **not** accounts. Windows: 7d / 30d / All.

## 22. Network

Default Direct. HTTP/SOCKS5: Name/Protocol/Host/Port/User/Pass. [测试连接] → Connected+Latency or fail. Fail → START disabled. Limited retry on NETWORK_ERROR only. NO CAPTCHA/rate-limit/login-block IP rotation.

## 23. Security / LIVE

Mode always LIVE for real browser runs. No Mock fallback. No auto Sign-up. No production card submit. No passwords/CVC in logs/exports/UI lists. Screenshots/traces only after stable page or on terminal FAIL/ERROR.

## 24. Install / Ops scripts

`install.sh`, `update.sh`, `backup.sh`, `restore.sh`, `status.sh`, `logs.sh`, `restart.sh`  
install: OS check, Docker, dir, .env, secret, DB, migrate, build, start, Chromium check, health. Print Version, Web URL, health, Mode LIVE.  
update: backup→pull→migrate→build→restart→health; fail must not leave half-upgraded.

## 25. Docker Compose services

frontend (3000), backend (8000), worker, sandbox (8080 internal). Shared `./data` volume. Network `payment-qa-net`.

## 26. Frontend pages (2.0)

`/` home, `/accounts`, `/test-data`, `/runs`, `/runs/[id]`, `/tasks`, `/settings`, `/login`  
Delete routes: environments, page-mapping, cases, sessions (complex), reports checklist, proxies standalone, import standalone, screenshots/logs as separate nav (artifacts via run details).

## 27. Worker behavior

Poll DB for QUEUED runs. Per item: launch Chromium (proxy if set), execute task path, write run_item + artifacts, update counts. Honor stop flag between items / at safe points. Always LIVE Playwright (PLAYWRIGHT_MOCK must not force PASS).

## 28. Seed data

- Admin from .env  
- Network: Direct (default)  
- Task: Preply Payment Page Smoke (Production, no card fill)  
- Task: Local Sandbox Card Binding (Sandbox, card fill)  

## 29. Versioning

Bump to 2.0.0 everywhere: README, Shell, config.app_version, package.json, install banners, health payload.

## 30. Tests (MUST actually run)

Backend pytest: import/normalize/dedupe, tasks, networks, run isolation, stop, export, cleanup, result codes, sandbox e2e with Playwright against sandbox.  
Frontend lint + build.  
Docker compose build + up + health.  
Fresh migrate. Account/test-data import. Task CRUD + URL test. Preply logic unit (HTML fixtures). Network direct. Real Chromium sandbox scenarios. Run isolation, STOP, export, delete, cleanup, restart persistence. LIVE no MOCK fallback.  
Anything not run → NOT TESTED. Never claim Preply production login PASS without real creds.

## 31. Git

Do not destroy history. Meaningful phase commits. Release 2.0.0 commit. Push origin/main when solid.

## 32. Safety refuse

Do NOT implement: production Preply card fill/submit, card probing, CAPTCHA bypass, auto IP rotate on login blocks.

## 33. Implementation phases

1. TASK_SPEC + TASK_STATE  
2. Fresh schema + Alembic + seed  
3. Backend API/services rewrite; delete dead 1.x  
4. Local sandbox service  
5. Worker state machine + Preply smoke + sandbox bind  
6. Frontend Shell + pages; delete old pages  
7. docker-compose, scripts, README, version  
8. Tests + E2E proof + Release commit + push  

