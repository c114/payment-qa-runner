"""Preply Production smoke: login + navigation + UI verification ONLY. No card fill/submit."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from app.services.result_codes import (
    ERROR_BAD_CREDENTIALS, ERROR_BROWSER, ERROR_LOGIN_TIMEOUT, ERROR_NETWORK,
    ERROR_TARGET, ERROR_UNKNOWN, SUCCESS_BOUND,
)

StepCb = Callable[[str, str], None]


def _safe_goto(page, url: str, timeout_ms: int = 25000) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        if "Execution context was destroyed" in str(e):
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        else:
            raise


def _wait_stable(page, seconds: float = 15.0) -> None:
    deadline = time.time() + seconds
    last_url = ""
    stable = 0
    while time.time() < deadline:
        try:
            url = page.url
            ready = page.evaluate("document.readyState")
            if url == last_url and ready == "complete":
                stable += 1
                if stable >= 2:
                    return
            else:
                stable = 0
                last_url = url
        except Exception as e:
            if "Execution context was destroyed" in str(e):
                time.sleep(0.5)
                continue
            time.sleep(0.4)
        time.sleep(0.5)


def run_preply_smoke(
    page,
    *,
    target_url: str,
    login_url: str,
    email: str,
    password: str,
    open_add_card: bool = True,
    on_step: Optional[StepCb] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    def step(state: str, msg: str) -> None:
        if on_step:
            on_step(state, msg)

    def stopped() -> bool:
        return bool(stop_check and stop_check())

    try:
        step("NAVIGATING", f"goto {target_url}")
        try:
            _safe_goto(page, target_url)
        except Exception as e:
            return {"code": ERROR_NETWORK, "reason": str(e)[:200]}

        step("WAITING_PAGE", "wait stable")
        _wait_stable(page, 15)

        if stopped():
            return {"code": "CANCELLED", "reason": "stopped"}

        # Redirected to login?
        url = page.url.lower()
        needs_auth = "login" in url or page.locator("input[type='password']").count() > 0
        # If payment methods already visible, skip auth
        body = ""
        try:
            body = page.inner_text("body")
        except Exception:
            pass
        if "Payment methods" in body or "Add card" in body:
            needs_auth = False

        if needs_auth:
            step("AUTH_REQUIRED", "login required")
            step("AUTHENTICATING", "filling login")
            try:
                # Prefer visible email/password
                email_sel = "input[type='email'], input[name='email'], input[autocomplete='email']"
                pass_sel = "input[type='password']"
                if page.locator(email_sel).count() == 0 and login_url:
                    _safe_goto(page, login_url)
                    _wait_stable(page, 12)
                page.fill(email_sel, email, timeout=10000)
                page.fill(pass_sel, password, timeout=10000)
                page.click("button[type='submit']", timeout=10000)
            except Exception as e:
                return {"code": ERROR_LOGIN_TIMEOUT, "reason": str(e)[:200]}
            _wait_stable(page, 15)
            if "login" in page.url.lower() and page.locator("input[type='password']").count() > 0:
                return {"code": ERROR_BAD_CREDENTIALS, "reason": "login did not complete"}
            step("AUTH_SUCCESS", "logged in")
            # Return to payments
            step("TARGET_LOADING", "return to payments")
            _safe_goto(page, target_url)
            _wait_stable(page, 15)
        else:
            step("AUTH_SUCCESS", "session or already on target")

        step("TARGET_READY", "checking payment UI")
        try:
            body = page.inner_text("body")
        except Exception as e:
            return {"code": ERROR_BROWSER, "reason": str(e)[:200]}

        has_pm = "Payment methods" in body or "payment method" in body.lower()
        has_add = "Add card" in body or page.locator("text=Add card").count() > 0
        if not has_pm and not has_add:
            return {"code": ERROR_TARGET, "reason": "Payment methods / Add card not found"}

        if open_add_card and has_add:
            step("FORM_OPEN", "open Add card (detect only)")
            try:
                page.locator("text=Add card").first.click(timeout=8000)
                _wait_stable(page, 10)
                body2 = page.inner_text("body")
                if "Save a payment card" in body2 or "card" in body2.lower():
                    step("COMPLETED", "Add card UI detected (no fill)")
                # Do NOT fill or submit on Production
            except Exception:
                pass  # optional modal — smoke still OK if payments visible

        step("COMPLETED", SUCCESS_BOUND)
        return {"code": SUCCESS_BOUND, "reason": "Payment page smoke OK (no card submit)"}

    except Exception as e:
        msg = str(e)
        if "net::" in msg:
            return {"code": ERROR_NETWORK, "reason": msg[:200]}
        return {"code": ERROR_BROWSER, "reason": msg[:200]}


def detect_preply_from_html(html: str, url: str = "") -> dict[str, Any]:
    """Unit-test helper: classify fixture HTML without browser."""
    low = (html or "").lower()
    if "login" in (url or "").lower() and "password" in low:
        return {"auth_required": True}
    if "payment methods" in low or "add card" in low:
        return {"target_ready": True, "has_add_card": "add card" in low}
    if "save a payment card" in low:
        return {"form_open": True}
    return {"unknown": True}
