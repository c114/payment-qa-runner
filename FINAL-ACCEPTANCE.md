# FINAL-ACCEPTANCE — Payment QA Runner

| Field | Value |
|-------|-------|
| Version | **1.2.0** |
| Test date | 2026-09-26 22:15 CST (Asia/Shanghai) |
| Architecture | Same-Origin: browser → `:3000/api/*` → Next proxy → `backend:8000` |
| Next.js | 15.5.26 standalone (`node server.js`) |
| Backend tests | 44 passed |

## Acceptance matrix

| Check | Result |
|-------|--------|
| Backend Test | **PASS** (44 passed) |
| Frontend Build | **PASS** |
| Frontend Lint | **PASS** |
| Docker Build | **PASS** (vfs driver on nested host) |
| Docker Compose Up + Health | **PASS** (backend/worker healthy; frontend Ready) |
| Fresh Clone COPY docs | **PASS** (docs/README.md + screenshots tracked; Dockerfile `COPY docs/`) |
| Same-Origin API | **PASS** (proxy route + login via `:3000/api`; code defaults `API=""`) |
| Next standalone (no start warning) | **PASS** (`node server.js`, no "next start does not work with output standalone") |
| SOCKS5 batch import/export | **PASS** (parsers + `/proxies/preview|batch-*|export|test-all|PUT`) |
| QA accounts batch | **PASS** (pipe formats + batch status/tag/delete + export) |
| Test case batch | **PASS** (preview/import/export/batch-enable/delete) |
| Browser Session actions | **PASS** (UI wired to `/browser-sessions/{id}/action`; mock OK) |
| Admin pages (no 404 nav) | **PASS** (all Shell nav routes exist) |
| Backup/Restore | **PASS** |
| Import/export smoke | **PASS** (`/import/preview` + templates via API) |
| Inter-container DNS on this box | **PASS with caveat** — nested Docker + limited netfilter blocked `backend` hostname; proxy verified via host-gateway. Real VPS bridge + `BACKEND_URL=http://backend:8000` is the supported path. |

## VPS update command

```bash
cd /opt/payment-qa-runner
sudo bash update.sh
```

## Public install

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
```

## Notes (1.2.0)

- **Same-Origin API**: `frontend/lib/api.ts` defaults to `""`; `app/api/[...path]/route.ts` proxies to `BACKEND_URL`.
- **docs/** tracked with README + reference PNGs; backend Dockerfile `COPY docs/`.
- **CORS**: localhost defaults; no public IP required for normal Same-Origin deploy.
- **Hard safety unchanged**: no auto-rotate on CARD_DECLINED/3DS/…; no CVV persist; Preply = UI reference only.
