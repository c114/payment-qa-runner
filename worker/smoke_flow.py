"""Preply Payment Page Smoke + Local Fixture flow (real Playwright).

Production smoke rules:
- Login + reach Payment methods + Add card (+ optional open modal)
- NEVER fill/submit card number/CVV on production
- No IP rotate on CAPTCHA / LOGIN_BLOCKED / BAD_CREDENTIALS
- Auto network retry ONLY for NETWORK_ERROR / CONNECTION_TIMEOUT / PROXY_DOWN
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("worker.smoke")

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CANDIDATES = [
    ROOT / "docs" / "fixtures" / "local-smoke.html",
    ROOT / "worker" / "fixtures" / "local-smoke.html",
    Path("/app/docs/fixtures/local-smoke.html"),
]


def resolve_fixture_url() -> str:
    # FIXTURE_BASE_URL overrides (http://...) when inter-container DNS works.
    # Default: local file:// fixture bundled in the worker/docs image.
    override = os.environ.get("FIXTURE_BASE_URL", "").strip()
    if override:
        base = override.rstrip("/")
        if not base.endswith(".html"):
            base = base + "/local-smoke.html"
        return base + "?page=payments"
    for p in FIXTURE_CANDIDATES:
        if p.is_file():
            return p.resolve().as_uri() + "?page=payments"
    raise FileNotFoundError("local-smoke.html fixture not found")


def resolve_fixture_login_url() -> str:
    u = resolve_fixture_url()
    return u.replace("page=payments", "page=login")


def session_path_for(account_id: int, session_dir: str) -> Path:
    d = Path(session_dir)
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except Exception:
        pass
    return d / f"account_{account_id}.json"


async def _visible_text(page, text: str) -> bool:
    try:
        loc = page.get_by_text(text, exact=False)
        if await loc.count() == 0:
            return False
        return await loc.first.is_visible()
    except Exception:
        return False


async def _has_role_or_text(page, *, role: str = None, name: str = None, text: str = None) -> bool:
    try:
        if role and name:
            loc = page.get_by_role(role, name=name)
            if await loc.count() > 0 and await loc.first.is_visible():
                return True
        if text:
            return await _visible_text(page, text)
    except Exception:
        pass
    return False


async def dismiss_cookie_if_blocking(page, log: Callable[[str], None]) -> None:
    """Dismiss cookie banner with Accept if it blocks targets."""
    for sel in ("#accept-cookies", "button:has-text('Accept')", "button:has-text('Accept all')"):
        try:
            btn = page.locator(sel)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click(timeout=3000, force=True)
                log(f"Dismissed cookie banner ({sel})")
                await page.wait_for_timeout(200)
                return
        except Exception:
            continue
    for label in ("Accept", "Accept all", "Accept All", "同意", "接受"):
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click(timeout=2000, force=True)
                log(f"Dismissed cookie banner ({label})")
                return
        except Exception:
            continue


async def payments_page_ready(page) -> bool:
    has_pm = await _has_role_or_text(page, role="heading", name="Payment methods", text="Payment methods")
    has_add = await _has_role_or_text(page, role="button", name="Add card", text="Add card")
    return has_pm and has_add


def url_is_login(url: str) -> bool:
    u = (url or "").lower()
    return "/login" in u or "page=login" in u


async def detect_login_problems(page) -> Optional[str]:
    # Prefer visible error nodes — raw HTML may contain hidden "Invalid password" copy
    try:
        err = page.locator("#login-error:not(.hidden), [data-qa='login-error'], .login-error")
        if await err.count() > 0 and await err.first.is_visible():
            return "BAD_CREDENTIALS"
    except Exception:
        pass
    # Visible text only
    visible = ""
    try:
        visible = (await page.inner_text("body")).lower()
    except Exception:
        try:
            visible = (await page.content()).lower()
        except Exception:
            pass
    for needle in ("captcha", "recaptcha", "hcaptcha", "cf-turnstile", "verify you are human"):
        if needle in visible:
            # Confirm a captcha widget is actually present
            try:
                if await page.locator("iframe[src*='captcha'], iframe[src*='recaptcha'], .g-recaptcha, [data-sitekey]").count() > 0:
                    return "CAPTCHA"
                if "verify you are human" in visible:
                    return "CAPTCHA"
            except Exception:
                return "CAPTCHA"
    for needle in ("too many attempts", "temporarily blocked", "account locked", "access denied"):
        if needle in visible:
            return "LOGIN_BLOCKED"
    for needle in ("invalid email or password", "incorrect password", "wrong password",
                   "invalid credentials", "login failed"):
        if needle in visible:
            # Ensure login form still visible (otherwise we already left login)
            try:
                if await page.locator("#login-form, input[type='password']").count() > 0:
                    if await page.locator("#login-form, input[type='password']").first.is_visible():
                        return "BAD_CREDENTIALS"
            except Exception:
                return "BAD_CREDENTIALS"
    return None



async def do_login(page, email: str, password: str, log: Callable[[str], None], timeout_ms: float = 30000) -> Optional[str]:
    """Fill login form. Returns error code or None on apparent success."""
    await dismiss_cookie_if_blocking(page, log)
    log("Filling login form")
    try:
        # Fast path: JS set values (works on file:// and http fixtures)
        found = await page.evaluate(
            """([em, pw]) => {
              const e = document.querySelector('#email, input[type=email], input[name=email]');
              const p = document.querySelector('#password, input[type=password]');
              if (!e || !p) return false;
              e.focus(); e.value = em; e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true}));
              p.focus(); p.value = pw; p.dispatchEvent(new Event('input', {bubbles:true})); p.dispatchEvent(new Event('change', {bubbles:true}));
              return true;
            }""",
            [email, password],
        )
        if not found:
            log("Login inputs not found")
            return "PAGE_ERROR"
        log("Credentials set via JS")
        # Submit
        clicked = await page.evaluate(
            """() => {
              const btn = document.querySelector('button[type=submit], #login-form button');
              if (btn) { btn.click(); return 'click'; }
              const form = document.getElementById('login-form') || document.querySelector('form');
              if (form && form.requestSubmit) { form.requestSubmit(); return 'submit'; }
              if (form) { form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true})); return 'event'; }
              return null;
            }"""
        )
        log(f"Login submit via {clicked}")
        if not clicked:
            return "PAGE_ERROR"
    except Exception as e:
        log(f"Login error: {e}")
        return "PAGE_ERROR"

    await page.wait_for_timeout(800)
    problem = await detect_login_problems(page)
    if problem:
        return problem
    return None


async def optional_open_add_card(page, log: Callable[[str], None], screenshot_dir: Path) -> List[str]:
    shots: List[str] = []
    log("Optional: clicking Add card")
    try:
        btn = page.get_by_role("button", name="Add card")
        if await btn.count() == 0:
            btn = page.get_by_text("Add card", exact=False)
        await btn.first.click(timeout=10000, force=True)
        await page.wait_for_timeout(500)
        modal_ok = await _visible_text(page, "Save a payment card")
        if not modal_ok:
            # still screenshot
            pass
        shot = screenshot_dir / f"add_card_modal_{int(time.time())}.png"
        await page.screenshot(path=str(shot), full_page=True)
        shots.append(str(shot))
        log("Add card modal screenshot saved (no card fill)")
    except Exception as e:
        log(f"Optional Add card phase skipped: {e}")
    return shots


async def run_smoke(
    *,
    start_url: str,
    email: Optional[str],
    password: Optional[str],
    storage_state_path: Optional[Path],
    screenshot_dir: Path,
    trace_dir: Path,
    log: Callable[[str], None],
    set_step: Callable[[str], None],
    proxy_cfg: Optional[dict] = None,
    timeout_sec: float = 30.0,
    open_modal: bool = True,
    is_local_fixture: bool = False,
    browser_debug: bool = False,
    require_account: bool = True,
) -> Dict[str, Any]:
    """Execute smoke flow. Returns result dict with status/actual/steps/screenshots/trace."""
    from playwright.async_api import async_playwright

    timeline: List[dict] = []
    shots: List[str] = []
    t0 = time.time()
    timeout_ms = timeout_sec * 1000
    trace_path = trace_dir / f"trace_{int(time.time())}.zip"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    if is_local_fixture:
        try:
            # If no storage yet, open login page directly (avoids client-side redirect race)
            has_state = bool(storage_state_path and storage_state_path.is_file())
            start_url = resolve_fixture_url() if has_state else resolve_fixture_login_url()
            log(f"Using local fixture: {start_url}")
        except FileNotFoundError as e:
            return _err("PAGE_ERROR", str(e), t0, timeline, shots)

    if require_account and not email:
        return _err("ACCOUNT_NOT_READY", "No account email", t0, timeline, shots)

    actual = "UNKNOWN"
    status = "ERROR"
    error_code = None
    error_message = None
    saved_state = False

    try:
        async with async_playwright() as p:
            set_step("Starting Chromium")
            log("Chromium started")
            timeline.append({"step": "chromium_start", "ok": True})

            browser = await p.chromium.launch(headless=True)
            ctx_kwargs: Dict[str, Any] = {}
            if proxy_cfg:
                ctx_kwargs["proxy"] = proxy_cfg

            loaded_state = False
            if storage_state_path and storage_state_path.is_file():
                try:
                    ctx_kwargs["storage_state"] = str(storage_state_path)
                    loaded_state = True
                    log(f"Storage loaded: {storage_state_path.name}")
                    timeline.append({"step": "storage_loaded", "ok": True})
                except Exception as e:
                    log(f"Storage load failed: {e}")

            context = await browser.new_context(**ctx_kwargs)
            # Trace always for evidence
            await context.tracing.start(screenshots=True, snapshots=True, sources=False)
            page = await context.new_page()

            set_step("Opening URL")
            log(f"Opening URL: {start_url}")
            try:
                await page.goto(start_url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as e:
                err = str(e).lower()
                code = "CONNECTION_TIMEOUT" if "timeout" in err else (
                    "PROXY_DOWN" if "proxy" in err else "NETWORK_ERROR"
                )
                await _safe_shot(page, screenshot_dir, "nav_fail", shots)
                await context.tracing.stop(path=str(trace_path))
                await browser.close()
                return _err(code, str(e), t0, timeline, shots, trace=str(trace_path))

            await dismiss_cookie_if_blocking(page, log)
            timeline.append({"step": "navigate", "ok": True, "url": page.url})

            # Case A: already on payments
            if await payments_page_ready(page):
                log("TARGET_PAGE_READY (existing session)")
                set_step("TARGET_PAGE_READY")
                actual = "TARGET_PAGE_READY"
                status = "PASS"
                error_code = "TARGET_PAGE_READY"
            elif url_is_login(page.url) or await _visible_text(page, "Log in") or await _visible_text(page, "Log In"):
                log("Redirected to login / AUTH_REQUIRED")
                set_step("AUTH_REQUIRED")
                timeline.append({"step": "auth_required", "ok": True})

                if loaded_state and storage_state_path:
                    # SESSION_EXPIRED — clear and login once
                    log("SESSION_EXPIRED — clearing prior storage_state")
                    try:
                        storage_state_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    # continue to login once

                if not email or not password:
                    await _safe_shot(page, screenshot_dir, "no_account", shots)
                    await context.tracing.stop(path=str(trace_path))
                    await browser.close()
                    return _err("ACCOUNT_NOT_READY", "Login required but no credentials", t0, timeline, shots, trace=str(trace_path))

                login_err = await do_login(page, email, password, log, timeout_ms)
                if login_err:
                    log(f"Login failed: {login_err}")
                    await _safe_shot(page, screenshot_dir, f"login_{login_err.lower()}", shots)
                    await context.tracing.stop(path=str(trace_path))
                    await browser.close()
                    return _err(login_err, login_err, t0, timeline, shots, trace=str(trace_path))

                # Re-open TARGET
                set_step("Re-open TARGET")
                log("Re-opening TARGET after login")
                target = start_url
                if is_local_fixture:
                    target = resolve_fixture_url()
                await page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
                await dismiss_cookie_if_blocking(page, log)

                # Wait for Payment methods + Add card
                ready = False
                for _ in range(20):
                    if await payments_page_ready(page):
                        ready = True
                        break
                    # still on login?
                    if url_is_login(page.url):
                        problem = await detect_login_problems(page)
                        if problem:
                            await _safe_shot(page, screenshot_dir, problem.lower(), shots)
                            await context.tracing.stop(path=str(trace_path))
                            await browser.close()
                            return _err(problem, problem, t0, timeline, shots, trace=str(trace_path))
                    await page.wait_for_timeout(500)

                if not ready:
                    await _safe_shot(page, screenshot_dir, "not_ready", shots)
                    await context.tracing.stop(path=str(trace_path))
                    await browser.close()
                    return _err("PAGE_ERROR", "Payment methods not visible after login", t0, timeline, shots, trace=str(trace_path))

                log("TARGET_PAGE_READY")
                set_step("TARGET_PAGE_READY")
                actual = "TARGET_PAGE_READY"
                status = "PASS"
                error_code = "TARGET_PAGE_READY"

                # Save storage_state
                if storage_state_path:
                    try:
                        await context.storage_state(path=str(storage_state_path))
                        try:
                            os.chmod(storage_state_path, 0o600)
                        except Exception:
                            pass
                        saved_state = True
                        log(f"storage_state saved: {storage_state_path.name}")
                    except Exception as e:
                        log(f"storage_state save failed: {e}")
            else:
                # Unexpected page
                await _safe_shot(page, screenshot_dir, "unexpected", shots)
                problem = await detect_login_problems(page)
                code = problem or "PAGE_ERROR"
                await context.tracing.stop(path=str(trace_path))
                await browser.close()
                return _err(code, f"Unexpected page: {page.url}", t0, timeline, shots, trace=str(trace_path))

            # Optional Add card modal (NO fill)
            if status == "PASS" and open_modal:
                set_step("Optional Add card")
                shots += await optional_open_add_card(page, log, screenshot_dir)

            # Final PASS screenshot
            if status == "PASS":
                shot = screenshot_dir / f"pass_final_{int(time.time())}.png"
                try:
                    await page.screenshot(path=str(shot), full_page=True)
                    shots.append(str(shot))
                    log("Final PASS screenshot saved")
                except Exception:
                    pass
                log("PASS")
                set_step("PASS")

            await context.tracing.stop(path=str(trace_path))
            await browser.close()
            timeline.append({"step": "done", "ok": status == "PASS"})

    except Exception as e:
        err = str(e).lower()
        if "proxy" in err:
            code = "PROXY_DOWN"
        elif "timeout" in err:
            code = "CONNECTION_TIMEOUT"
        elif "net" in err:
            code = "NETWORK_ERROR"
        else:
            code = "BROWSER_CRASH" if "browser" in err else "PAGE_ERROR"
        return _err(code, str(e), t0, timeline, shots)

    return {
        "expected": "TARGET_PAGE_READY",
        "actual": actual,
        "status": status,
        "error_code": error_code,
        "duration_ms": (time.time() - t0) * 1000,
        "steps": timeline,
        "screenshot_paths": shots,
        "error_message": error_message,
        "pan_masked": None,
        "trace_path": str(trace_path) if trace_path.exists() else None,
        "saved_state": saved_state,
        "is_mock": False,
    }


async def _safe_shot(page, screenshot_dir: Path, tag: str, shots: List[str]) -> None:
    try:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        shot = screenshot_dir / f"{tag}_{int(time.time())}.png"
        await page.screenshot(path=str(shot), full_page=True)
        shots.append(str(shot))
    except Exception:
        pass


def _err(code: str, msg: str, t0: float, timeline: list, shots: list, trace: str = None) -> dict:
    return {
        "expected": "TARGET_PAGE_READY",
        "actual": code,
        "status": "ERROR" if code not in ("TARGET_PAGE_READY",) else "PASS",
        "error_code": code,
        "duration_ms": (time.time() - t0) * 1000,
        "steps": timeline,
        "screenshot_paths": shots,
        "error_message": msg,
        "pan_masked": None,
        "trace_path": trace,
        "saved_state": False,
        "is_mock": False,
    }
