def test_health_live(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["version"] == "2.0.0"
    assert j["mode"] == "LIVE"
    assert j["detail"]["mock_fallback"] is False


def test_login_and_me(client, auth_headers):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@example.com"


def test_seeded_tasks_and_direct_network(client, auth_headers):
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    keys = {t["key"] for t in tasks}
    assert "preply-payment-smoke" in keys
    assert "local-sandbox-bind" in keys
    preply = next(t for t in tasks if t["key"] == "preply-payment-smoke")
    assert preply["env_type"] == "Production"
    assert preply["allow_card_fill"] is False
    sand = next(t for t in tasks if t["key"] == "local-sandbox-bind")
    assert sand["allow_card_fill"] is True

    nets = client.get("/api/networks", headers=auth_headers).json()
    assert any(n["name"] == "Direct" and n["protocol"] == "direct" for n in nets)


def test_account_import_preview_confirm_export(client, auth_headers):
    text = "qa1@test.com|pass1\nqa1@test.com|pass1\nbad\nqa2@test.com----pass2\n"
    prev = client.post("/api/accounts/import-preview", headers=auth_headers, json={"text": text}).json()
    assert prev["valid"] == 2
    assert prev["dupe"] >= 1
    assert prev["error"] >= 1

    conf = client.post("/api/accounts/import-confirm", headers=auth_headers, json={"text": text, "skip_dupes": True}).json()
    assert conf["created"] == 2

    rows = client.get("/api/accounts", headers=auth_headers).json()
    assert len(rows) >= 2
    assert all("password" not in r for r in rows)

    exp = client.get("/api/accounts/export", headers=auth_headers)
    assert exp.status_code == 200
    assert "password" not in exp.text.lower() or "password" in exp.text.split("\n")[0].lower()  # header ok? we don't include password col
    assert "pass1" not in exp.text


def test_test_data_import_safe_export(client, auth_headers):
    text = "4242424242424242|12/30|123\n4000000000000002|06/29|456\n"
    prev = client.post("/api/test-data/import-preview", headers=auth_headers, json={"text": text}).json()
    assert prev["valid"] == 2
    conf = client.post("/api/test-data/import-confirm", headers=auth_headers, json={"text": text}).json()
    assert conf["created"] == 2
    rows = client.get("/api/test-data", headers=auth_headers).json()
    assert all("cvc" not in r and "pan_enc" not in r for r in rows)
    assert rows[0]["pan_masked"].startswith("****")
    exp = client.get("/api/test-data/export-safe", headers=auth_headers)
    assert "123" not in exp.text  # cvc
    assert "4242424242424242" not in exp.text  # full pan


def test_task_create_edit_production_no_fill(client, auth_headers):
    r = client.post("/api/tasks", headers=auth_headers, json={
        "name": "Prod Smoke", "env_type": "Production",
        "base_url": "https://example.com", "target_url": "https://example.com/pay",
        "task_type": "card_bind",
    })
    assert r.status_code == 200
    t = r.json()
    assert t["allow_card_fill"] is False
    assert t["task_type"] == "smoke"


def test_network_direct_test(client, auth_headers):
    nets = client.get("/api/networks", headers=auth_headers).json()
    direct = next(n for n in nets if n["protocol"] == "direct")
    r = client.post(f"/api/networks/{direct['id']}/test", headers=auth_headers)
    assert r.status_code == 200
    # may OK or FAIL depending on network egress — just ensure shape
    assert "ok" in r.json()


def test_run_isolation_and_pairing(client, auth_headers):
    # import 2 accounts + 1 card → max 1 for sandbox task
    client.post("/api/accounts/import-confirm", headers=auth_headers, json={
        "text": "r1@t.com|p\nr2@t.com|p\n"
    })
    client.post("/api/test-data/import-confirm", headers=auth_headers, json={
        "text": "4242424242424242|12/30|123\n"
    })
    accs = client.get("/api/accounts", headers=auth_headers).json()
    tds = client.get("/api/test-data", headers=auth_headers).json()
    client.post("/api/accounts/select", headers=auth_headers, json={"ids": [a["id"] for a in accs], "selected": True})
    client.post("/api/test-data/select", headers=auth_headers, json={"ids": [t["id"] for t in tds], "selected": True})

    tasks = client.get("/api/tasks", headers=auth_headers).json()
    sand = next(t for t in tasks if t["key"] == "local-sandbox-bind")
    nets = client.get("/api/networks", headers=auth_headers).json()
    direct = next(n for n in nets if n["protocol"] == "direct")
    # mark network OK so START allowed
    from app.core.database import SessionLocal
    # via API test endpoint
    client.post(f"/api/networks/{direct['id']}/test", headers=auth_headers)

    r = client.post("/api/runs", headers=auth_headers, json={"task_id": sand["id"], "network_id": direct["id"]})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["progress_total"] == 1  # min(2 accounts, 1 card)
    assert len(run["items"]) == 1
    assert run["mode"] == "LIVE"

    # second run is isolated
    r2 = client.post("/api/runs", headers=auth_headers, json={"task_id": sand["id"], "network_id": direct["id"]})
    assert r2.status_code == 200
    assert r2.json()["id"] != run["id"]


def test_stop_run(client, auth_headers):
    client.post("/api/accounts/import-confirm", headers=auth_headers, json={"text": "s@t.com|p\n"})
    accs = client.get("/api/accounts", headers=auth_headers).json()
    client.post("/api/accounts/select", headers=auth_headers, json={"ids": [accs[0]["id"]], "selected": True})
    tasks = client.get("/api/tasks", headers=auth_headers).json()
    smoke = next(t for t in tasks if t["key"] == "preply-payment-smoke")
    nets = client.get("/api/networks", headers=auth_headers).json()
    direct = next(n for n in nets if n["protocol"] == "direct")
    client.post(f"/api/networks/{direct['id']}/test", headers=auth_headers)
    run = client.post("/api/runs", headers=auth_headers, json={"task_id": smoke["id"], "network_id": direct["id"]}).json()
    st = client.post(f"/api/runs/{run['id']}/stop", headers=auth_headers)
    assert st.status_code == 200
    assert st.json()["status"] in ("STOPPING", "CANCELLED", "COMPLETED")


def test_cleanup_preview(client, auth_headers):
    r = client.get("/api/cleanup/preview?window=30d", headers=auth_headers)
    assert r.status_code == 200
    assert "runs" in r.json()


def test_result_codes_never_unknown_success():
    from app.services.result_codes import never_unknown_as_success, ERROR_UNKNOWN, SUCCESS_BOUND
    assert never_unknown_as_success(None) == ERROR_UNKNOWN
    assert never_unknown_as_success("") == ERROR_UNKNOWN
    assert never_unknown_as_success("PASS") == ERROR_UNKNOWN
    assert never_unknown_as_success("SUCCESS") == ERROR_UNKNOWN
    assert never_unknown_as_success(SUCCESS_BOUND) == SUCCESS_BOUND


def test_preply_html_fixture_detect():
    from worker.flows.preply_smoke import detect_preply_from_html
    assert detect_preply_from_html("<html>Payment methods Add card</html>")["target_ready"] is True
    assert detect_preply_from_html("<html><input type=password></html>", url="https://x/login")["auth_required"] is True
