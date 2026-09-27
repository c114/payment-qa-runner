"""1.3.0 quick-run, parsers ----, no force-mock, smoke helpers."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.parsers import parse_qa_accounts
from app.services.error_codes import (
    LIVE_TESTING_DISABLED, ENVIRONMENT_NOT_ALLOWED, message_zh, NO_PROXY_ROTATE,
)
from app.services.comparison import forbid_proxy_rotate_on, may_auto_switch_network


def test_parse_email_pipe_password():
    r = parse_qa_accounts("a@test.com|Secret123\n")
    assert len(r.items) == 1
    assert r.items[0]["email"] == "a@test.com"
    assert r.items[0]["password"] == "Secret123"


def test_parse_email_dash_password():
    r = parse_qa_accounts("b@test.com----Secret456\n")
    assert len(r.items) == 1
    assert r.items[0]["email"] == "b@test.com"
    assert r.items[0]["password"] == "Secret456"


def test_error_codes_chinese():
    assert "Mock" in message_zh("MOCK_MODE") or "Mock" in message_zh("MOCK_MODE") or "模式" in message_zh("MOCK_MODE")
    assert "LIVE_TESTING" in message_zh(LIVE_TESTING_DISABLED) or "实时" in message_zh(LIVE_TESTING_DISABLED)


def test_no_proxy_rotate_on_auth_failures():
    for code in ("CAPTCHA", "LOGIN_BLOCKED", "BAD_CREDENTIALS"):
        assert forbid_proxy_rotate_on(code) or code in NO_PROXY_ROTATE


def test_network_retry_only_network_codes():
    assert may_auto_switch_network("NETWORK_ERROR")
    assert may_auto_switch_network("CONNECTION_TIMEOUT")
    assert may_auto_switch_network("PROXY_DOWN")
    assert not may_auto_switch_network("CAPTCHA")
    assert not may_auto_switch_network("BAD_CREDENTIALS")
    assert not may_auto_switch_network("DECLINED")


def test_fixture_exists():
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "docs" / "fixtures" / "local-smoke.html",
        root / "worker" / "fixtures" / "local-smoke.html",
    ]
    assert any(p.is_file() for p in paths), "local-smoke.html missing"


def test_runner_has_no_force_mock_fallback():
    root = Path(__file__).resolve().parents[2]
    text = (root / "worker" / "runner.py").read_text()
    assert "Live testing refused" not in text or "force mock" not in text.lower().split("never")[0]
    # Stronger: the exact old log string must be gone
    assert "Live testing refused:" not in text
    assert "— force mock" not in text


def test_smoke_flow_module_importable():
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from worker.smoke_flow import url_is_login, resolve_fixture_url
    assert url_is_login("https://preply.com/en/login?next=/payments")
    assert url_is_login("file:///tmp/x.html?page=login")
    assert not url_is_login("https://preply.com/en/settings/payments")
    url = resolve_fixture_url()
    assert url.startswith("file:") and "local-smoke" in url


def _login(client):
    from app.core.config import get_settings
    s = get_settings()
    r = client.post("/api/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health_mode_and_quick_run(client):
    """API: health has mode; task presets seeded; quick-run creates run."""
    h = client.get("/api/health")
    assert h.status_code == 200
    body = h.json()
    assert str(body.get("version", "")).startswith("1.3")
    assert body.get("mode") in ("LIVE", "MOCK")
    assert "backend" in body and "worker" in body

    headers = _login(client)
    presets = client.get("/api/task-presets", headers=headers)
    assert presets.status_code == 200
    data = presets.json()
    assert isinstance(data, list)
    keys = {p["key"] for p in data}
    assert "local_chromium_smoke" in keys or "preply_payment_smoke" in keys

    imp = client.post(
        "/api/accounts/import",
        headers=headers,
        json={"text": "local-qa@test.local|LocalPass123"},
    )
    assert imp.status_code == 200

    accounts = client.get("/api/accounts", headers=headers).json()
    assert len(accounts) >= 1
    aid = accounts[0]["id"]

    local = next((p for p in data if p["key"] == "local_chromium_smoke"), data[0])
    qr = client.post(
        "/api/quick-run",
        headers=headers,
        json={"task_id": local["id"], "account_ids": [aid], "force_mock": True},
    )
    assert qr.status_code == 200, qr.text
    run_id = qr.json()["run_id"]
    st = client.get(f"/api/quick-run/{run_id}", headers=headers)
    assert st.status_code == 200
    assert st.json()["run_id"] == run_id
    assert st.json()["status"] in ("QUEUED", "RUNNING", "COMPLETED", "FAILED")
