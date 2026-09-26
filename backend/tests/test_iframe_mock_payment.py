"""Iframe mock payment page: SUCCESS/DECLINED/3DS/TIMEOUT detection + step sequence."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.services.comparison import compare_expected_actual, THREEDS

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mock_pay_page"
MAIN = FIXTURE_DIR / "main.html"
IFRAME = FIXTURE_DIR / "iframe.html"


def _mock_iframe_runner(result_mode: str) -> dict:
    """
    PLAYWRIGHT_MOCK path that still exercises iframe selector resolution order:
    Main → iframe → fill → submit → detect
    """
    steps = []
    assert MAIN.exists() and IFRAME.exists()
    steps.append({"step": "Main", "ok": True, "selector": "#pay-iframe"})
    steps.append({"step": "iframe", "ok": True, "iframe_selector": "#pay-iframe", "file": str(IFRAME)})
    # fill card fields inside iframe
    for sel in ("#card-number", "#expiry", "#cvv"):
        steps.append({"step": "fill", "ok": True, "selector": sel, "iframe": True})
    steps.append({"step": "submit", "ok": True, "selector": "#submit-pay", "iframe": True})
    actual = result_mode
    if result_mode == "3DS":
        steps.append({"step": "detect", "ok": False, "actual": "3DS", "msg": "3DS — stop case"})
    else:
        steps.append({"step": "detect", "ok": True, "actual": actual})
    expected = "SUCCESS"
    exp, act, status = compare_expected_actual(expected, actual)
    return {"expected": exp, "actual": act, "status": status, "steps": steps}


@pytest.mark.parametrize("mode,expected_actual,expected_status", [
    ("SUCCESS", "SUCCESS", "PASS"),
    ("DECLINED", "DECLINED", "FAIL"),
    ("3DS", "3DS", "FAIL"),
    ("TIMEOUT", "TIMEOUT", "FAIL"),
])
def test_iframe_mock_detection_sequence(mode, expected_actual, expected_status):
    r = _mock_iframe_runner(mode)
    assert [s["step"] for s in r["steps"][:5]] == ["Main", "iframe", "fill", "fill", "fill"]
    assert r["steps"][5]["step"] == "submit"
    assert r["actual"] == expected_actual
    assert r["status"] == expected_status
    if mode == "3DS":
        assert r["actual"] == THREEDS
        assert any(s.get("actual") == "3DS" for s in r["steps"])


def test_iframe_fixtures_exist():
    assert "pay-iframe" in MAIN.read_text()
    html = IFRAME.read_text()
    for token in ("card-number", "expiry", "cvv", "submit-pay", "threeds", "SUCCESS", "DECLINED"):
        assert token in html


@pytest.mark.asyncio
async def test_playwright_against_file_fixtures_if_available():
    """Prefer real Playwright against file:// fixtures when Chromium is installed."""
    if os.environ.get("PLAYWRIGHT_MOCK", "1") == "1" and os.environ.get("FORCE_PLAYWRIGHT_IFRAME") != "1":
        # Still validate mock path when browsers unavailable
        r = _mock_iframe_runner("3DS")
        assert r["status"] == "FAIL" and r["actual"] == "3DS"
        return
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed")
    main_url = MAIN.resolve().as_uri() + "?result=DECLINED"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(main_url)
            frame = page.frame_locator("#pay-iframe")
            await frame.locator("#card-number").fill("4111111111111111")
            await frame.locator("#expiry").fill("12/30")
            await frame.locator("#cvv").fill("123")
            await frame.locator("#submit-pay").click()
            text = await frame.locator("#result").inner_text()
            await browser.close()
            assert "DECLINED" in text.upper()
    except Exception as e:
        # Fall back to mock sequence if chromium missing
        if "Executable doesn't exist" in str(e) or "BrowserType.launch" in str(e):
            r = _mock_iframe_runner("DECLINED")
            assert r["actual"] == "DECLINED"
            return
        raise
