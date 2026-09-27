"""Full card binding against Local Sandbox (and similar Sandbox/QA tasks)."""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Optional

from app.services.result_codes import (
    ERROR_BAD_CREDENTIALS, ERROR_BROWSER, ERROR_LOGIN_TIMEOUT, ERROR_NETWORK,
    ERROR_TARGET, ERROR_UNKNOWN, FAIL_3DS, FAIL_DECLINED, FAIL_INVALID, SUCCESS_BOUND,
)


StepCb = Callable[[str, str], None]  # state, message


def _ret(page, code: str, reason: str) -> dict[str, Any]:
    url = ""
    try:
        url = page.url or ""
    except Exception:
        pass
    return {"code": code, "reason": reason, "final_url": url}


def _safe_goto(page, url: str, timeout_ms: int = 20000) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        msg = str(e)
        if "Execution context was destroyed" in msg or "navigation" in msg.lower():
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        else:
            raise


def _wait_stable(page, seconds: float = 12.0) -> None:
    """Poll for stable page after navigation — avoid mid-nav screenshots."""
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
                time.sleep(0.4)
                continue
            time.sleep(0.3)
            continue
        time.sleep(0.5)


def run_sandbox_bind(
    page,
    *,
    base_url: str,
    login_url: str,
    target_url: str,
    email: str,
    password: str,
    pan: str,
    expiry: str,
    cvc: str,
    on_step: Optional[StepCb] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> dict[str, Any]:
    """Login → Payment → Add Card → Fill → Submit → Parse. Returns result dict."""

    def step(state: str, msg: str) -> None:
        if on_step:
            on_step(state, msg)

    def stopped() -> bool:
        return bool(stop_check and stop_check())

    try:
        step("STARTING_BROWSER", "browser ready")
        if stopped():
            return _ret(page, "CANCELLED", "stopped")

        step("NAVIGATING", f"goto {target_url}")
        try:
            _safe_goto(page, target_url)
        except Exception as e:
            if "net::" in str(e) or "TIMEOUT" in str(e).upper():
                return _ret(page, ERROR_NETWORK, str(e)[:200])
            return _ret(page, ERROR_BROWSER, str(e)[:200])

        step("WAITING_PAGE", "wait stable")
        _wait_stable(page, 12)

        # Auth required?
        if "/login" in page.url or page.locator("input[type='password'], [data-testid='password']").count() > 0:
            step("AUTH_REQUIRED", "login page detected")
            step("AUTHENTICATING", "fill credentials")
            try:
                page.fill("input[type='email'], input[name='email'], [data-testid='email']", email, timeout=8000)
                page.fill("input[type='password'], input[name='password'], [data-testid='password']", password, timeout=8000)
                page.click("button[type='submit'], [data-testid='login-submit']", timeout=8000)
            except Exception as e:
                return _ret(page, ERROR_LOGIN_TIMEOUT, f"login form: {e}"[:200])

            _wait_stable(page, 12)
            if page.locator("[data-testid='login-error']").count() > 0:
                return _ret(page, ERROR_BAD_CREDENTIALS, "Bad credentials")
            if "/login" in page.url:
                return _ret(page, ERROR_BAD_CREDENTIALS, "still on login")
            step("AUTH_SUCCESS", "authenticated")
        else:
            step("AUTH_SUCCESS", "already authenticated / session")

        if stopped():
            return _ret(page, "CANCELLED", "stopped")

        # Ensure on payments
        step("TARGET_LOADING", "open payments")
        if "/settings/payments" not in page.url or "/add" in page.url:
            _safe_goto(page, target_url)
            _wait_stable(page, 10)

        # Detect payment methods
        body = ""
        try:
            body = page.inner_text("body")
        except Exception:
            pass
        if "Payment methods" not in body and page.locator("[data-testid='payment-methods']").count() == 0:
            # maybe need navigate again
            _safe_goto(page, target_url)
            _wait_stable(page, 8)
            try:
                body = page.inner_text("body")
            except Exception:
                body = ""
            if "Payment methods" not in body and page.locator("[data-testid='payment-methods']").count() == 0:
                return _ret(page, ERROR_TARGET, "Payment methods not found")

        step("TARGET_READY", "payment methods visible")

        # Open Add card
        add = page.locator("[data-testid='add-card'], a[href*='payments/add'], text=Add card").first
        try:
            add.click(timeout=8000)
        except Exception:
            _safe_goto(page, f"{base_url.rstrip('/')}/settings/payments/add")
        _wait_stable(page, 8)

        step("FORM_OPEN", "add card form")
        if page.locator("[data-testid='card-number'], input[name='number'], input[autocomplete='cc-number']").count() == 0:
            return _ret(page, ERROR_TARGET, "card form not found")

        # FILL — required for success
        step("FILLING", "fill card fields")
        page.fill("[data-testid='card-number'], input[name='number'], input[autocomplete='cc-number']", pan)
        page.fill("[data-testid='expiry'], input[name='expiry'], input[autocomplete='cc-exp']", expiry)
        page.fill("[data-testid='cvc'], input[name='cvc'], input[autocomplete='cc-csc']", cvc)

        step("SUBMITTING", "submit card")
        page.click("[data-testid='save-card'], button[type='submit']")

        step("WAITING_RESULT", "wait result")
        # Don't screenshot mid-nav; wait stable
        try:
            page.wait_for_url("**/settings/payments/result**", timeout=20000)
        except Exception:
            pass
        _wait_stable(page, 10)

        # Parse result
        result_el = page.locator("[data-testid='result']")
        code_text = ""
        reason = ""
        try:
            if result_el.count() > 0:
                code_text = (result_el.inner_text() or "").strip().upper()
            reason_el = page.locator("[data-testid='result-reason']")
            if reason_el.count() > 0:
                reason = (reason_el.inner_text() or "").strip()
            body = page.inner_text("body")
        except Exception as e:
            if "Execution context was destroyed" in str(e):
                _wait_stable(page, 5)
                try:
                    body = page.inner_text("body")
                    code_text = body.split("\n")[0][:40].upper() if body else ""
                except Exception:
                    return _ret(page, ERROR_UNKNOWN, "context destroyed parsing")
            else:
                return _ret(page, ERROR_BROWSER, str(e)[:200])

        # 3DS detection
        if code_text == "3DS_REQUIRED" or page.locator("[data-testid='threeds'], iframe[src*='3ds']").count() > 0:
            return _ret(page, FAIL_3DS, reason or "3DS challenge required")

        if code_text == "BOUND" or "Card saved" in (reason or "") or page.locator("[data-testid='success']").count() > 0:
            step("COMPLETED", SUCCESS_BOUND)
            return _ret(page, SUCCESS_BOUND, reason or "Card bound")

        if code_text == "DECLINED" or "declined" in (reason or "").lower():
            return _ret(page, FAIL_DECLINED, reason or "Declined")

        if code_text == "INVALID_DATA" or "invalid" in (reason or "").lower():
            return _ret(page, FAIL_INVALID, reason or "Invalid data")

        if code_text == "TIMEOUT":
            return _ret(page, ERROR_NETWORK, reason or "Timeout")

        # UNKNOWN — never SUCCESS
        return _ret(page, ERROR_UNKNOWN, reason or f"Unrecognized: {code_text or body[:80]}")

    except Exception as e:
        msg = str(e)
        if "net::" in msg:
            return _ret(page, ERROR_NETWORK, msg[:200])
        return _ret(page, ERROR_BROWSER, msg[:200])
