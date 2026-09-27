"""E2E against Local Sandbox with embedded uvicorn."""
from __future__ import annotations

import importlib.util
import os
import socket
import threading
import time
from pathlib import Path

import pytest


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _load_sandbox_app():
    path = Path(__file__).resolve().parents[2] / "sandbox" / "main.py"
    spec = importlib.util.spec_from_file_location("sandbox_main", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.app


@pytest.fixture(scope="module")
def sandbox_url():
    env = os.environ.get("SANDBOX_E2E_URL")
    if env:
        yield env
        return

    import uvicorn
    port = _free_port()
    sandbox_app = _load_sandbox_app()
    config = uvicorn.Config(sandbox_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(80):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    else:
        pytest.fail("sandbox failed to start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def test_sandbox_bind_outcomes(sandbox_url):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from worker.flows.sandbox_bind import run_sandbox_bind
    from app.services.result_codes import (
        SUCCESS_BOUND, FAIL_DECLINED, FAIL_3DS, FAIL_INVALID, ERROR_UNKNOWN,
    )

    cases = [
        ("4242424242424242", SUCCESS_BOUND),
        ("4000000000000002", FAIL_DECLINED),
        ("4000000000000003", FAIL_3DS),
        ("4000000000000001", FAIL_INVALID),
        ("4000000000000099", ERROR_UNKNOWN),
    ]
    base = sandbox_url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for pan, expected in cases:
            context = browser.new_context()
            page = context.new_page()
            result = run_sandbox_bind(
                page,
                base_url=base,
                login_url=f"{base}/login",
                target_url=f"{base}/settings/payments",
                email="qa@sandbox.test",
                password="password",
                pan=pan,
                expiry="12/30",
                cvc="123",
            )
            context.close()
            assert result["code"] == expected, f"pan={pan} got={result}"
        context = browser.new_context()
        page = context.new_page()
        result = run_sandbox_bind(
            page,
            base_url=base,
            login_url=f"{base}/login",
            target_url=f"{base}/settings/payments",
            email="qa2@sandbox.test",
            password="password",
            pan="4000000000009999",
            expiry="12/30",
            cvc="123",
        )
        context.close()
        assert result["code"] == SUCCESS_BOUND, result
        browser.close()


def test_sandbox_bad_credentials(sandbox_url):
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from worker.flows.sandbox_bind import run_sandbox_bind
    from app.services.result_codes import ERROR_BAD_CREDENTIALS

    base = sandbox_url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = run_sandbox_bind(
            page,
            base_url=base,
            login_url=f"{base}/login",
            target_url=f"{base}/settings/payments",
            email="bad@sandbox.test",
            password="x",
            pan="4242424242424242",
            expiry="12/30",
            cvc="123",
        )
        browser.close()
        assert result["code"] == ERROR_BAD_CREDENTIALS, result
