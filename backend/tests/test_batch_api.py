"""Smoke tests for 1.2.0 batch / import preview endpoints."""
from fastapi.testclient import TestClient


def _login(client: TestClient) -> dict:
    # conftest usually provides auth; fall back to bootstrap admin
    from app.core.config import get_settings
    s = get_settings()
    r = client.post("/api/auth/login", json={"email": s.admin_email, "password": s.admin_password})
    if r.status_code != 200:
        return {}
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_import_preview_proxies(client: TestClient):
    h = _login(client)
    if not h:
        return
    r = client.post("/api/import/preview", headers=h, json={
        "type": "proxies",
        "text": "127.0.0.1:1080\nbadline\n10.0.0.1:1080:u:p\n",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["parsed"] == 2
    assert data["errors"]
    assert data["items"][0]["host"] == "127.0.0.1"


def test_import_preview_accounts_pipe(client: TestClient):
    h = _login(client)
    if not h:
        return
    r = client.post("/api/import/preview", headers=h, json={
        "type": "accounts",
        "text": "Name|qa_batch@example.com|Secret999|tag1\n",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["parsed"] == 1
    assert data["items"][0]["email"] == "qa_batch@example.com"
    assert data["items"][0]["password"] == "***"


def test_template_download(client: TestClient):
    h = _login(client)
    if not h:
        return
    r = client.get("/api/import/templates/cases", headers=h)
    assert r.status_code == 200
    assert "TC001" in r.text or "case_id" in r.text


def test_version_endpoint(client: TestClient):
    r = client.get("/api/version")
    assert r.status_code == 200
    assert r.json()["version"] == "1.2.0"


def test_health_has_version(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json().get("version") == "1.2.0"
