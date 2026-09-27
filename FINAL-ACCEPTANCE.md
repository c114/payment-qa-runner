# FINAL-ACCEPTANCE — Payment QA Runner 1.3.1

| Field | Value |
|-------|-------|
| Version | **1.3.1** |
| Test date | 2026-09-27 Asia/Shanghai (UTC+8) |
| Architecture | Same-Origin: browser → `:3000/api/*` → Next proxy → `backend:8000` |
| Next.js | standalone (`node server.js`) |
| Default mode | `PLAYWRIGHT_MOCK=0` (LIVE) |

## 1.3.1 highlights

- Delayed-redirect waiter (`wait_for_page_state`) — Preply white-screen mid-nav no longer early PAGE_ERROR
- Legacy TestRun NULL columns → `/api/test-runs` returns 200
- Data Management page (cleanup with confirm + DB backup; preserves Admin/Env/NetworkProfile/TaskPreset)
- Rich result detail (error_code / final_url / page_title / screenshot / trace)
- Field help (是什么/是否必填/格式/示例/怎么操作)
- No Live→Mock fallback (1.3.0 behavior preserved)

## Acceptance matrix

| Check | Result |
|-------|--------|
| Backend pytest | **PASS** (59 passed) |
| Frontend lint / build | **PASS** |
| Docker compose build | **PASS** (backend + worker) |
| `/api/test-runs` with legacy NULLs | **PASS** (200) |
| Existing DB / settings preserved | **PASS** (additive migration 004 only) |
| External Preply account login | **NOT TESTED** (no real Preply credentials) |
| Force-mock / Live→Mock fallback | **PASS** (still absent) |
| Same-Origin API + standalone `node server.js` | **PASS** (unchanged) |

## User commands

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
cd /opt/payment-qa-runner && sudo bash update.sh
```

Simple START: 登录 → 导入账号 (`email@example.com|password` / `email@example.com----password`) → 选任务 → 开始。
