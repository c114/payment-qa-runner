"""1.3.1: null TestRun compat, delayed redirect AUTH_REQUIRED, cleanup preserves, waiter transient."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _login(client):
    from app.core.config import get_settings
    from app.api import routes as routes_mod
    # Clear in-memory rate limit so full suite doesn't 429
    routes_mod._LOGIN_ATTEMPTS.clear()
    s = get_settings()
    r = client.post("/api/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_legacy_null_testrun_list_returns_200(client):
    """Old rows with NULL account_ids/run_mode/is_mock must not 500."""
    from app.core.database import engine, SessionLocal
    from app.models.models import Environment

    headers = _login(client)
    db = SessionLocal()
    try:
        env = db.query(Environment).first()
        assert env is not None
        # Insert via raw SQL to force NULLs bypassing ORM defaults
        # Insert a normal row, then force the 1.3.0-era nullable columns back to NULL
        # (mirrors upgraded DBs where ADD COLUMN left NULLs on old rows).
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO test_runs (name, environment_id, status, progress_done, progress_total, "
                    "pass_count, fail_count, error_count, run_count, proxy_pool_ids, case_ids, live_log, "
                    "account_ids, run_mode, is_mock, created_at) "
                    "VALUES ('legacy-null', :eid, 'COMPLETED', 0, 0, 0, 0, 0, '1', '[]', '[]', '[]', "
                    "'[]', 'workflow', 0, CURRENT_TIMESTAMP)"
                ),
                {"eid": env.id},
            )
            # SQLite allows NULL into columns added as nullable; recreate table slice via UPDATE
            # after relaxing — use a temp approach: UPDATE through ORM expire + raw if possible.
            # For columns that are NOT NULL in create_all, simulate via serialize_run Fake +
            # also UPDATE the ones that migration 003 added as nullable.
            try:
                conn.execute(text(
                    "UPDATE test_runs SET account_ids = NULL, run_mode = NULL, is_mock = NULL "
                    "WHERE name = 'legacy-null'"
                ))
            except Exception:
                pass
    finally:
        db.close()

    # Also unit-check serializer with explicit Nones (covers proxy_pool_ids/case_ids/live_log)
    from types import SimpleNamespace
    from app.api.routes import serialize_run
    from datetime import datetime, timezone
    fake = SimpleNamespace(
        id=99999, name="fake-null", environment_id=env.id, account_id=None,
        network_profile_id=None, proxy_pool_ids=None, case_ids=None, run_count="1",
        status="COMPLETED", progress_done=0, progress_total=0, pass_count=0, fail_count=0,
        error_count=0, current_case_id=None, task_preset_id=None, account_ids=None,
        current_account=None, current_step=None, run_mode=None, is_mock=None,
        error_code=None, live_log=None, started_at=None, finished_at=None,
        created_at=datetime.now(timezone.utc),
    )
    out = serialize_run(fake)
    assert out.account_ids == []
    assert out.proxy_pool_ids == []
    assert out.case_ids == []
    assert out.live_log == []
    assert out.run_mode == "workflow"
    assert out.is_mock is False

    r = client.get("/api/test-runs", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    legacy = next((x for x in rows if x.get("name") == "legacy-null"), None)
    assert legacy is not None
    assert legacy["account_ids"] == []
    assert legacy["run_mode"] == "workflow"
    assert legacy["is_mock"] is False


def test_data_cleanup_preserves_core(client):
    headers = _login(client)
    before = client.get("/api/data-management/summary", headers=headers)
    assert before.status_code == 200, before.text
    b = before.json()
    assert b["environments"] >= 1
    assert b["network_profiles"] >= 1
    assert b["admins"] >= 1
    assert b["task_presets"] >= 1

    # Create a disposable result path: cleanup results only
    r = client.post(
        "/api/data-management/cleanup",
        headers=headers,
        json={"confirm": True, "results": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "Environment" in body["preserved"] or "Environment" in str(body["preserved"])
    assert "AdminUser" in body["preserved"]
    assert "NetworkProfile" in body["preserved"]
    assert "TaskPreset" in body["preserved"]

    after = client.get("/api/data-management/summary", headers=headers).json()
    assert after["environments"] == b["environments"]
    assert after["network_profiles"] == b["network_profiles"]
    assert after["admins"] == b["admins"]
    assert after["task_presets"] == b["task_presets"]

    # confirm required
    bad = client.post(
        "/api/data-management/cleanup",
        headers=headers,
        json={"confirm": False, "runs": True},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_wait_for_page_state_delayed_redirect_auth_required():
    """Local HTML redirects after ~1.5s to /login form — must get AUTH_REQUIRED, not early PAGE_ERROR."""
    from worker.smoke_flow import wait_for_page_state

    # Serve a tiny site so URL contains /login after redirect
    site = FIXTURE_DIR / "_redir_site"
    site.mkdir(exist_ok=True)
    (site / "payments.html").write_text(
        """<!DOCTYPE html><html><head><title>Payments</title>
<script>setTimeout(function(){ location.href = '/en/login?next=/payments'; }, 1200);</script>
</head><body><p>Loading…</p></body></html>""",
        encoding="utf-8",
    )
    (site / "en").mkdir(exist_ok=True)
    # SimpleHTTPRequestHandler serves files; map /en/login via login.html + redirect trick:
    # Use a custom handler
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(site), **kw)

        def do_GET(self):
            if self.path.startswith("/en/login"):
                body = b"""<!DOCTYPE html><html><head><title>Log in</title></head><body>
<h1>Log in</h1>
<form id="login-form">
<label>Email <input id="email" type="email" name="email" placeholder="Email" /></label>
<label>Password <input id="password" type="password" name="password" /></label>
<button type="submit">Log in</button>
</form></body></html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/payments"):
                self.path = "/payments.html"
            return super().do_GET()

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    logs = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{port}/payments", wait_until="domcontentloaded")
            # Immediate classify would miss login — waiter must wait
            t0 = time.time()
            state = await wait_for_page_state(page, logs.append, timeout_sec=12.0, poll_ms=300)
            elapsed = time.time() - t0
            await browser.close()
        assert state == "AUTH_REQUIRED", f"got {state}, logs={logs}"
        assert elapsed >= 0.8, "should have waited for redirect"
        assert state != "PAGE_ERROR"
    finally:
        httpd.shutdown()


@pytest.mark.asyncio
async def test_wait_for_page_state_context_destroyed_continues():
    """Transient 'Execution context was destroyed' must continue waiting, not PAGE_ERROR early."""
    from worker.smoke_flow import wait_for_page_state

    class FakeLocator:
        def __init__(self, n=0):
            self._n = n
        async def count(self):
            return self._n
        @property
        def first(self):
            return self
        async def is_visible(self):
            return self._n > 0

    class FakePage:
        def __init__(self):
            self.calls = 0
            self.url = "https://preply.com/en/settings/payments"
        def locator(self, *a, **k):
            return FakeLocator(0)
        def get_by_text(self, *a, **k):
            return FakeLocator(0)
        def get_by_role(self, *a, **k):
            return FakeLocator(0)
        def get_by_label(self, *a, **k):
            return FakeLocator(0)
        def get_by_placeholder(self, *a, **k):
            return FakeLocator(0)
        async def inner_text(self, *a, **k):
            self.calls += 1
            if self.calls <= 3:
                raise Exception("Execution context was destroyed, most likely because of a navigation")
            # After transient errors, land on login
            self.url = "https://preply.com/en/login?next=/payments"
            return "log in"
        async def content(self):
            return await self.inner_text("body")
        async def wait_for_timeout(self, ms):
            await asyncio.sleep(ms / 1000.0)

    # Monkeypatch helpers used inside waiter to eventually see login form
    import worker.smoke_flow as sf

    page = FakePage()
    logs = []

    orig_payments = sf.payments_page_ready
    orig_login_form = sf.login_form_visible
    orig_detect = sf.detect_login_problems

    async def fake_payments(p):
        return False

    async def fake_login_form(p):
        p.calls += 1
        if p.calls <= 3:
            raise Exception("Execution context was destroyed, most likely because of a navigation")
        return True

    async def fake_detect(p):
        return None

    sf.payments_page_ready = fake_payments
    sf.login_form_visible = fake_login_form
    sf.detect_login_problems = fake_detect
    try:
        state = await wait_for_page_state(page, logs.append, timeout_sec=8.0, poll_ms=50)
    finally:
        sf.payments_page_ready = orig_payments
        sf.login_form_visible = orig_login_form
        sf.detect_login_problems = orig_detect

    assert state == "AUTH_REQUIRED", f"got {state}, logs={logs}"
    assert any("transient" in (x or "").lower() for x in logs), logs


def test_version_is_131(client):
    h = client.get("/api/health")
    assert h.status_code == 200
    assert str(h.json().get("version", "")).startswith("1.3.1")


@pytest.mark.asyncio
async def test_live_local_fixture_screenshot_and_trace(tmp_path):
    """PLAYWRIGHT_MOCK=0 local fixture still produces real PNG + trace.zip."""
    os.environ["PLAYWRIGHT_MOCK"] = "0"
    from worker.smoke_flow import run_smoke, resolve_fixture_url

    shot_dir = tmp_path / "shots"
    trace_dir = tmp_path / "traces"
    logs = []
    steps = []

    result = await run_smoke(
        start_url=resolve_fixture_url(),
        email="local-qa@test.local",
        password="LocalPass123",
        storage_state_path=tmp_path / "state.json",
        screenshot_dir=shot_dir,
        trace_dir=trace_dir,
        log=logs.append,
        set_step=steps.append,
        timeout_sec=45.0,
        open_modal=True,
        is_local_fixture=True,
        require_account=False,
    )
    assert result["status"] == "PASS", result
    assert result.get("is_mock") is False
    shots = result.get("screenshot_paths") or []
    assert shots, f"expected screenshots, logs={logs[-10:]}"
    assert any(Path(p).is_file() and Path(p).stat().st_size > 0 for p in shots)
    tp = result.get("trace_path")
    assert tp and Path(tp).is_file() and Path(tp).stat().st_size > 0, result
