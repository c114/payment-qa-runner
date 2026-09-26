# FINAL-ACCEPTANCE — Payment QA Runner

| Field | Value |
|-------|-------|
| Version | **1.1.0** |
| Test date | 2026-09-26 20:04 CST (Asia/Shanghai) |
| Next.js | 15.5.26 (14.2.35 EOL left residual CVEs; 15.5.26 builds clean; Next 16 needs ESLint 9 — not applied) |
| Backend tests | 35 passed |

## Acceptance matrix

| Check | Result |
|-------|--------|
| Backend Test | **PASS** |
| Frontend Build | **PASS** |
| Frontend Lint | **PASS** |
| Security Audit (npm audit) | **FAIL** |
| Proxy Test (unit) | **PASS** |
| Browser Worker Test | **PASS** |
| Backup/Restore | **PASS** |
| Docker Static Validation | **PASS** |
| Docker Runtime Validation | **NOT TESTED** |

### Notes

- **Security Audit FAIL**: After upgrading to Next.js **15.5.26** / `eslint-config-next@15.5.26`, `npm audit` still reports **2** issues (1 moderate, 1 high) from Next’s nested `postcss`. Fix requires `next@16.3.6` + ESLint ≥9 (breaking). 14.2.35 still had many more advisories.
- **Docker Runtime NOT TESTED**: no `docker` CLI on this host. Static validation: Python YAML parse of `docker-compose.yml` (named network `payment-qa-net`, healthchecks, single `./data` volume, worker `depends_on` healthy).
- **Backup/Restore PASS**: marker file in `data/` → `./backup.sh` → delete marker → `./restore.sh <backup>` → marker restored. Backup now packs `data` + `.env.example` + `.env` in one tarball (fixed broken `tar rzf` append).
- **Proxy Test PASS**: `test_socks5_probe.py` (greeting/auth builders, AUTH_ERROR mock server, HANDSHAKE_ERROR, timeout).
- **Browser Worker Test PASS**: mock workflow + iframe mock payment + 3DS rule tests; worker marks sessions STALE on restart and heartbeats owned sessions.
- **Iframe mock**: fixtures under `backend/tests/fixtures/mock_pay_page/`; sequence Main→iframe→fill→submit→detect; SUCCESS/DECLINED/3DS/TIMEOUT asserted.
- **Health shape**: `/api/health` returns `backend|database|worker|browser_worker` each with `{status, last_seen}`.
- **Production defaults**: `PLAYWRIGHT_MOCK=1`, `LIVE_TESTING_ENABLED=false`; worker refuses live payment unless flag + sandbox/staging/internal + allowlist.

## VPS next commands

```bash
cd /path/to/payment-qa-runner
cp .env.example .env
# edit ADMIN_PASSWORD away from ChangeMe_*; deploy.sh generates JWT/SESSION/ENCRYPTION secrets
chmod +x deploy.sh update.sh backup.sh restore.sh scripts/vps-preflight.sh
./scripts/vps-preflight.sh
./deploy.sh
# optional HTTPS: install Caddy and use deploy/Caddyfile.example with DOMAIN=qa.example.com
# STRICT_PRODUCTION=1 ./deploy.sh   # refuses example admin password
curl -s http://localhost:8000/api/health | jq .
```
