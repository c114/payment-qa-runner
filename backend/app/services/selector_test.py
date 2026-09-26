"""Live selector test (locate only)."""
from __future__ import annotations

from typing import Any, Optional

from app.services.allowlist import assert_navigation_allowed


def test_selector_live(env, selector: str, selector_type: str, iframe_selector: Optional[str] = None) -> dict[str, Any]:
    assert_navigation_allowed(env.base_url, env.allowed_domains or [])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError("playwright not installed") from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(env.base_url, wait_until="domcontentloaded", timeout=20000)
        target = page
        if iframe_selector:
            frame = page.frame_locator(iframe_selector)
            target = frame
        count = 0
        if selector_type == "text":
            loc = target.get_by_text(selector, exact=False) if hasattr(target, "get_by_text") else page.get_by_text(selector, exact=False)
            count = loc.count()
        elif selector_type == "playwright":
            loc = page.locator(selector)
            count = loc.count()
        else:
            loc = target.locator(selector) if hasattr(target, "locator") else page.locator(selector)
            count = loc.count()
        browser.close()
        return {"ok": True, "found": count > 0, "count": count, "message": f"found {count}"}
