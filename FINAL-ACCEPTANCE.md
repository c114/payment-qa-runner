# FINAL-ACCEPTANCE — Payment QA Runner 1.3.0

| Field | Value |
|-------|-------|
| Version | **1.3.0** |
| Test date | 2026-09-27 Asia/Shanghai (UTC+8) |
| Architecture | Same-Origin: browser → `:3000/api/*` → Next proxy → `backend:8000` |
| Next.js | standalone (`node server.js`) |
| Default mode | `PLAYWRIGHT_MOCK=0` (LIVE) |

## Acceptance matrix

| Check | Result |
|-------|--------|
| Backend pytest | **PASS** (53 passed) |
| Frontend lint | **PASS** |
| Frontend build | **PASS** |
| Docker compose build | **PASS** |
| Docker runtime / health | **PASS** (`mode=LIVE`, `version=1.3.0`, worker ok) |
| Fresh install scripts | **PASS** (install.sh MOCK=0, secrets, docs COPY) |
| Existing DB preserved | **PASS** (`data/payment_qa.db` kept; alembic 003 additive) |
| Quick Run API | **PASS** (queue → worker claim → status) |
| Live Chromium local fixture | **PASS** (success=1, real PNG + trace.zip + storage_state) |
| External Preply account login | **NOT TESTED** (no real Preply credentials in env) |
| Force-mock removed | **PASS** (ERROR codes; no `Live testing refused → force mock`) |
| Mock/Live separation | **PASS** (health.mode LIVE\|MOCK; MOCK banner on UI) |
| Session persistence | **PASS** (`data/sessions/account_1.json`, mode 600) |
| Same-Origin API | **PASS** (login via `:3000/api`; empty `NEXT_PUBLIC_API_URL`) |
| Next standalone | **PASS** (`CMD node server.js`) |
| docs/ tracked for COPY | **PASS** (fixtures + README) |

## User commands

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
cd /opt/payment-qa-runner && sudo bash update.sh
```

Simple START: 登录 → 导入账号 (`email|password` / `email----password`) → 选任务 → 开始。
