"""Playwright worker: DB-polled job consumer with allowlist + safety rules."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow importing backend package
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import ensure_data_dirs, get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import decrypt_secret, mask_pan, never_persist_cvv, redact_dict
from app.models.models import (
    AppLog, BrowserSession, Environment, NetworkProfile, PageMapping, PayrailsConfig,
    QAAccount, RunnerSettings, Socks5Proxy, SystemSettings, TaskPreset, TestCase, TestResult, TestRun,
    WorkflowStep,
)
from app.services.error_codes import (
    LIVE_TESTING_DISABLED, ENVIRONMENT_NOT_ALLOWED, ACCOUNT_NOT_READY,
    PAYMENT_FILL_NOT_ALLOWED, message_zh,
)
from app.seed.bootstrap import seed_all
from app.services.allowlist import assert_navigation_allowed, is_url_allowed
from app.services.comparison import (
    THREEDS, NETWORK_ERROR, PAGE_ERROR, BROWSER_CRASH, PROXY_DOWN, CONNECTION_TIMEOUT,
    UNKNOWN, compare_expected_actual, may_auto_switch_network, forbid_proxy_rotate_on,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worker")


WORKER_ID = f"worker-{os.getpid()}"


def heartbeat(db) -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == "worker_heartbeat").first()
    val = {"ts": time.time(), "pid": os.getpid(), "worker_id": WORKER_ID}
    if not row:
        db.add(SystemSettings(key="worker_heartbeat", value=val))
    else:
        row.value = val
    # Touch heartbeat file for docker healthcheck
    settings = get_settings()
    hb_path = Path(os.environ.get("WORKER_HEARTBEAT_FILE") or (Path(settings.log_dir) / "worker.heartbeat"))
    try:
        hb_path.parent.mkdir(parents=True, exist_ok=True)
        hb_path.write_text(f"{time.time()}\n{WORKER_ID}\n")
    except Exception:
        pass
    # Heartbeat all owned / active sessions
    now = datetime.now(timezone.utc)
    for s in db.query(BrowserSession).filter(
        BrowserSession.status.in_(["OPEN", "READY", "RUNNING"])
    ).all():
        s.last_heartbeat = now
        s.worker_id = s.worker_id or WORKER_ID
    db.commit()


def mark_sessions_stale_on_startup(db) -> None:
    """Worker restarted — previous RUNNING/READY/OPEN sessions are STALE."""
    now = datetime.now(timezone.utc)
    q = db.query(BrowserSession).filter(
        BrowserSession.status.in_(["OPEN", "READY", "RUNNING"])
    )
    n = 0
    for s in q.all():
        s.status = "STALE"
        s.browser_state = "crashed"
        s.last_activity = now
        n += 1
    if n:
        db.add(AppLog(level="WARN", source="worker", message=f"Marked {n} sessions STALE on startup", meta={}))
    db.commit()


def is_mock_mode() -> bool:
    """Mock only for pytest/CI/dev/PLAYWRIGHT_MOCK=1/admin explicit mock. Default production: 0."""
    settings = get_settings()
    raw = os.environ.get("PLAYWRIGHT_MOCK", str(settings.playwright_mock if settings.playwright_mock is not None else 0))
    try:
        return bool(int(raw))
    except Exception:
        return str(raw).lower() in ("1", "true", "yes")


def live_testing_enabled() -> bool:
    settings = get_settings()
    return os.environ.get("LIVE_TESTING_ENABLED", str(settings.live_testing_enabled)).lower() in ("1", "true", "yes")


def smoke_live_allowed(env: Optional[Environment], task: Optional[TaskPreset]) -> tuple[bool, str, str]:
    """Production/local smoke (no card fill) is allowed even when LIVE_TESTING_ENABLED is false.
    Returns (ok, error_code, reason).
    """
    task_type = (task.task_type if task else "smoke") or "smoke"
    allow_fill = bool(task.allow_card_fill) if task else False
    env_type = (env.env_type if env else (task.env_scope if task else "production")) or "production"
    env_type = env_type.lower()

    if task_type in ("smoke", "local_fixture") and not allow_fill:
        # UI smoke / local fixture — real Chromium OK without LIVE_TESTING_ENABLED
        if env and env.allowed_domains is not None and len(env.allowed_domains or []) == 0 and env_type not in ("local", "internal"):
            return False, ENVIRONMENT_NOT_ALLOWED, "allowed_domains empty"
        return True, "", "ok"

    # payment_fill requires LIVE_TESTING + sandbox|staging|internal
    if not live_testing_enabled():
        return False, LIVE_TESTING_DISABLED, "LIVE_TESTING_ENABLED is false"
    if env_type not in ("sandbox", "staging", "internal"):
        return False, ENVIRONMENT_NOT_ALLOWED, f"env_type={env_type} not sandbox/staging/internal"
    if env and not (env.allowed_domains or []):
        return False, ENVIRONMENT_NOT_ALLOWED, "allowed_domains empty — fail closed"
    if env and env.base_url and not is_url_allowed(env.base_url, env.allowed_domains or []):
        return False, ENVIRONMENT_NOT_ALLOWED, "base_url outside allowed_domains"
    return True, "", "ok"


def live_testing_allowed(env: Environment) -> tuple[bool, str]:
    """Legacy helper for payment fill workflows."""
    ok, code, reason = smoke_live_allowed(env, None)
    # Without task, treat as payment-fill policy (strict)
    if not live_testing_enabled():
        return False, LIVE_TESTING_DISABLED
    if (env.env_type or "").lower() not in ("sandbox", "staging", "internal"):
        return False, ENVIRONMENT_NOT_ALLOWED
    if not (env.allowed_domains or []):
        return False, "allowed_domains empty — fail closed"
    if not is_url_allowed(env.base_url, env.allowed_domains or []):
        return False, "base_url outside allowed_domains"
    return True, "ok"


def append_live_log(run: TestRun, msg: str) -> None:
    log = list(run.live_log or [])
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": msg})
    run.live_log = log[-200:]


def set_run_step(run: TestRun, step: str) -> None:
    run.current_step = step


class MockBrowser:
    """CI-friendly mock that simulates workflow without real Chromium payment."""

    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = allowed_domains
        self.closed = False

    async def navigate(self, url: str):
        assert_navigation_allowed(url, self.allowed_domains)

    async def close(self):
        self.closed = True


async def mock_run_case(
    case: TestCase,
    env: Environment,
    payrails: PayrailsConfig,
    mappings: Dict[str, PageMapping],
    steps: List[WorkflowStep],
    screenshot_dir: Path,
) -> Dict[str, Any]:
    """Simulate Expected→Actual based on payment_test_ref heuristics for CI."""
    timeline = []
    t0 = time.time()
    browser = MockBrowser(env.allowed_domains or [])
    try:
        await browser.navigate(env.base_url)
        timeline.append({"step": "navigate", "ok": True, "ms": 10})
    except PermissionError as e:
        return {
            "expected": case.expected_result, "actual": "PAGE_ERROR", "status": "ERROR",
            "duration_ms": (time.time() - t0) * 1000, "steps": timeline,
            "screenshot_paths": [], "error_message": str(e), "pan_masked": case.pan_masked,
        }

    ref = (case.payment_test_ref or "").upper()
    expected = case.expected_result
    # Heuristic mock outcomes from ref name
    if "3DS" in ref or "THREE" in ref:
        actual = THREEDS
    elif "DECLINE" in ref or "DECLINED" in ref:
        actual = "DECLINED"
    elif "INVALID_CVV" in ref or "BAD_CVV" in ref:
        actual = "INVALID_CVV"
    elif "INVALID" in ref:
        actual = "INVALID_CARD"
    elif "INSUFFICIENT" in ref:
        actual = "INSUFFICIENT_FUNDS"
    elif "NETWORK" in ref:
        actual = NETWORK_ERROR
    elif "TIMEOUT" in ref:
        actual = "TIMEOUT"
    elif "SUCCESS" in ref or "OK" in ref or not ref:
        actual = "SUCCESS"
    else:
        actual = expected  # default: match expected for happy-path refs

    for st in steps:
        timeline.append({"step": st.step_key, "action": st.action, "ok": True, "ms": 5})
        if st.action == "detect" and actual == THREEDS:
            timeline.append({"step": "threeds_abort", "ok": False, "ms": 1, "msg": "3DS detected — end case, do not solve OTP"})
            break

    exp, act, status = compare_expected_actual(expected, actual)
    shots = []
    policy = set((os.environ.get("SCREENSHOT_POLICY") or "FAIL,ERROR,3DS").split(","))
    if status in policy or act in policy or (act == THREEDS and "3DS" in policy):
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        shot = screenshot_dir / f"mock_{case.case_id}_{int(time.time())}.png"
        # Minimal PNG header
        shot.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        shots.append(str(shot))

    await browser.close()
    return {
        "expected": exp, "actual": act, "status": status,
        "duration_ms": (time.time() - t0) * 1000, "steps": timeline,
        "screenshot_paths": shots, "error_message": None, "pan_masked": case.pan_masked,
    }


async def live_run_case(
    case: TestCase,
    env: Environment,
    account: Optional[QAAccount],
    network: Optional[NetworkProfile],
    proxy: Optional[Socks5Proxy],
    payrails: PayrailsConfig,
    mappings: Dict[str, PageMapping],
    steps: List[WorkflowStep],
    screenshot_dir: Path,
    timeout_sec: float,
) -> Dict[str, Any]:
    """Real Playwright path with allowlist enforcement."""
    from playwright.async_api import async_playwright

    timeline: List[dict] = []
    t0 = time.time()
    shots: List[str] = []
    actual = UNKNOWN
    cvv_memory: Optional[str] = None  # in-memory only

    proxy_cfg = None
    if network and network.mode == "proxy" and proxy:
        server = f"socks5://{proxy.host}:{proxy.port}"
        proxy_cfg = {"server": server}
        if proxy.username:
            proxy_cfg["username"] = proxy.username
            if proxy.password_enc:
                proxy_cfg["password"] = decrypt_secret(proxy.password_enc)

    # Resolve sandbox card from Payrails config by payment_test_ref
    card_data = (payrails.sandbox_cards or {}).get(case.payment_test_ref) or {}
    pan = card_data.get("pan") or card_data.get("number") or ""
    expiry = card_data.get("expiry") or case.expiry or ""
    cvv_memory = card_data.get("cvv") or card_data.get("cvc") or ""
    pan_masked = case.pan_masked or (mask_pan(pan) if pan else None)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(proxy=proxy_cfg)
            page = await context.new_page()

            async def guard(frame_url: str):
                if frame_url and frame_url.startswith("http"):
                    if not is_url_allowed(frame_url, env.allowed_domains or []):
                        raise PermissionError(f"Navigation refused outside allowlist: {frame_url}")

            page.on("framenavigated", lambda fr: asyncio.create_task(guard(fr.url)) if fr.url else None)

            for st in steps:
                if not st.enabled:
                    continue
                step_t = time.time()
                try:
                    if st.action == "navigate":
                        assert_navigation_allowed(env.base_url, env.allowed_domains or [])
                        await page.goto(env.base_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                    elif st.action == "click":
                        for key in st.mapping_keys:
                            m = mappings.get(key)
                            if not m or not m.selector:
                                continue
                            loc = _locator(page, m)
                            await loc.first.click(timeout=timeout_sec * 1000)
                    elif st.action == "fill":
                        if account:
                            email_m = mappings.get("login.email_input")
                            pass_m = mappings.get("login.password_input")
                            sub_m = mappings.get("login.submit_btn")
                            if email_m and email_m.selector:
                                await _locator(page, email_m).first.fill(account.email)
                            if pass_m and pass_m.selector:
                                await _locator(page, pass_m).first.fill(decrypt_secret(account.password_enc))
                            if sub_m and sub_m.selector:
                                await _locator(page, sub_m).first.click()
                    elif st.action == "fill_card":
                        # Fill card fields; CVV from memory only
                        for key, value in (
                            ("payment.card_number", pan),
                            ("payment.expiry", expiry),
                            ("payment.cvv", cvv_memory or ""),
                        ):
                            m = mappings.get(key)
                            if m and m.selector and value:
                                await _locator(page, m).first.fill(value)
                        cvv_memory = None  # discard immediately after fill attempt
                    elif st.action == "detect":
                        actual = await _detect_result(page, mappings, payrails)
                        if actual == THREEDS:
                            timeline.append({
                                "step": st.step_key, "ok": False,
                                "ms": (time.time() - step_t) * 1000,
                                "msg": "3DS detected — FAIL vs Expected (unless Expected=3DS), end case",
                            })
                            break
                    timeline.append({"step": st.step_key, "ok": True, "ms": (time.time() - step_t) * 1000})
                except PermissionError:
                    raise
                except Exception as e:
                    timeline.append({"step": st.step_key, "ok": False, "ms": (time.time() - step_t) * 1000, "error": str(e)})
                    actual = PAGE_ERROR
                    break

            await browser.close()
    except PermissionError as e:
        cvv_memory = None
        return {
            "expected": case.expected_result, "actual": PAGE_ERROR, "status": "ERROR",
            "duration_ms": (time.time() - t0) * 1000, "steps": timeline,
            "screenshot_paths": shots, "error_message": str(e), "pan_masked": pan_masked,
        }
    except Exception as e:
        cvv_memory = None
        err = str(e).lower()
        if "proxy" in err:
            actual = PROXY_DOWN
        elif "timeout" in err:
            actual = CONNECTION_TIMEOUT
        elif "net" in err:
            actual = NETWORK_ERROR
        else:
            actual = BROWSER_CRASH if "browser" in err else PAGE_ERROR
        exp, act, status = compare_expected_actual(case.expected_result, actual)
        return {
            "expected": exp, "actual": act, "status": "ERROR" if act in (PAGE_ERROR, BROWSER_CRASH, NETWORK_ERROR) else status,
            "duration_ms": (time.time() - t0) * 1000, "steps": timeline,
            "screenshot_paths": shots, "error_message": str(e), "pan_masked": pan_masked,
        }
    finally:
        cvv_memory = None  # never leave CVV in memory longer than needed

    exp, act, status = compare_expected_actual(case.expected_result, actual)
    return {
        "expected": exp, "actual": act, "status": status,
        "duration_ms": (time.time() - t0) * 1000, "steps": timeline,
        "screenshot_paths": shots, "error_message": None, "pan_masked": pan_masked,
    }


def _locator(page, m: PageMapping):
    target = page
    if m.iframe_selector:
        target = page.frame_locator(m.iframe_selector)
    if m.selector_type == "text":
        return target.get_by_text(m.selector, exact=False)
    return target.locator(m.selector)


async def _detect_result(page, mappings: Dict[str, PageMapping], payrails: PayrailsConfig) -> str:
    content = ""
    try:
        content = (await page.content()).lower()
    except Exception:
        pass
    # 3DS first — end immediately
    threeds_keys = ["result.threeds"] + list(payrails.threeds_selectors or [])
    for key in threeds_keys:
        if key.startswith("result."):
            m = mappings.get(key)
            sel = m.selector if m else ""
        else:
            sel = key
        if not sel:
            continue
        for part in sel.replace("|", ",").split(","):
            part = part.strip()
            if part and part.lower() in content:
                return THREEDS
            try:
                if await page.locator(part).count() > 0:
                    return THREEDS
            except Exception:
                pass

    checks = [
        ("SUCCESS", "result.success"),
        ("DECLINED", "result.declined"),
        ("INVALID_CARD", "result.invalid_card"),
        ("INVALID_CVV", "result.invalid_cvv"),
        ("INSUFFICIENT_FUNDS", "result.insufficient_funds"),
    ]
    for code, key in checks:
        m = mappings.get(key)
        if not m or not m.selector:
            continue
        for part in m.selector.replace("|", ",").split(","):
            part = part.strip().lower()
            if part and part in content:
                return code
    return UNKNOWN



async def process_smoke_run(
    db, run: TestRun, settings_obj: RunnerSettings,
    env, account, network, proxy, task, mock: bool,
    shot_root: Path, trace_root: Path,
) -> None:
    """One-click smoke / local_fixture quick-run across account_ids."""
    from app.core.security import decrypt_secret
    from worker.smoke_flow import run_smoke, session_path_for, resolve_fixture_url

    settings = get_settings()
    ok, err_code, reason = smoke_live_allowed(env, task)
    if not mock and not ok:
        append_live_log(run, f"ERROR {err_code}: {message_zh(err_code)} ({reason})")
        run.status = "FAILED"
        run.error_code = err_code
        run.error_count = (run.error_count or 0) + 1
        run.finished_at = datetime.now(timezone.utc)
        set_run_step(run, err_code)
        db.commit()
        return

    start_url = (task.start_url if task and task.start_url else None) or (env.base_url if env else "")
    is_local = (task.task_type == "local_fixture") if task else (run.run_mode == "local_fixture")
    open_modal = bool(task.open_add_card_modal) if task else True
    browser_debug = bool(int(os.environ.get("BROWSER_DEBUG", getattr(settings, "browser_debug", 0) or 0)))

    proxy_cfg = None
    if network and network.mode == "proxy" and proxy:
        proxy_cfg = {"server": f"socks5://{proxy.host}:{proxy.port}"}
        if proxy.username:
            proxy_cfg["username"] = proxy.username
            if proxy.password_enc:
                proxy_cfg["password"] = decrypt_secret(proxy.password_enc)

    # Resolve accounts: account_ids list, else single account_id, else all READY
    ids = list(run.account_ids or [])
    if not ids and run.account_id:
        ids = [run.account_id]
    accounts = []
    for aid in ids:
        a = db.get(QAAccount, aid)
        if a:
            accounts.append(a)
    if not accounts and is_local:
        # Local fixture can run with a synthetic account (or none)
        accounts = [None]
    if not accounts:
        append_live_log(run, f"ERROR {ACCOUNT_NOT_READY}: {message_zh(ACCOUNT_NOT_READY)}")
        run.status = "FAILED"
        run.error_code = ACCOUNT_NOT_READY
        run.error_count = (run.error_count or 0) + 1
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    run.progress_total = len(accounts)
    db.commit()

    for acct in accounts:
        db.refresh(run)
        if run.status == "STOPPING":
            run.status = "STOPPED"
            append_live_log(run, "Stopped by admin")
            db.commit()
            return

        email = acct.email if acct else "qa@local.test"
        password = decrypt_secret(acct.password_enc) if acct else "local-pass"
        run.current_account = email
        set_run_step(run, "Starting")
        append_live_log(run, f"Account: {email}")
        db.commit()

        def _log(msg: str, _run=run, _db=db):
            append_live_log(_run, msg)
            try:
                _db.commit()
            except Exception:
                pass

        def _step(step: str, _run=run, _db=db):
            set_run_step(_run, step)
            try:
                _db.commit()
            except Exception:
                pass

        if mock:
            # Explicit mock path only
            append_live_log(run, "MOCK MODE simulating smoke PASS (not live Chromium)")
            result = {
                "expected": "TARGET_PAGE_READY", "actual": "TARGET_PAGE_READY", "status": "PASS",
                "duration_ms": 50, "steps": [{"step": "mock_smoke", "ok": True}],
                "screenshot_paths": [], "error_message": "MOCK MODE",
                "pan_masked": None, "error_code": "MOCK_MODE", "is_mock": True, "trace_path": None,
            }
            # Write a tiny mock screenshot marker so UI isn't empty
            shot_root.mkdir(parents=True, exist_ok=True)
            shot = shot_root / f"mock_{int(datetime.now(timezone.utc).timestamp())}.png"
            shot.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            result["screenshot_paths"] = [str(shot)]
        else:
            spath = None
            if acct:
                spath = session_path_for(acct.id, settings.session_dir)
                if acct.session_path:
                    spath = Path(acct.session_path)

            result = await run_smoke(
                start_url=start_url,
                email=email,
                password=password,
                storage_state_path=spath,
                screenshot_dir=shot_root / f"account_{acct.id if acct else 0}",
                trace_dir=trace_root / f"account_{acct.id if acct else 0}",
                log=_log,
                set_step=_step,
                proxy_cfg=proxy_cfg,
                timeout_sec=settings_obj.timeout_sec,
                open_modal=open_modal,
                is_local_fixture=is_local,
                browser_debug=browser_debug,
                require_account=not is_local,
            )

            # Update account session status
            if acct and not result.get("is_mock"):
                if result.get("saved_state") and spath and spath.is_file():
                    acct.session_status = "VALID"
                    acct.session_path = str(spath)
                    acct.session_updated_at = datetime.now(timezone.utc)
                    acct.last_login_status = "OK"
                elif result.get("error_code") == "SESSION_EXPIRED":
                    acct.session_status = "EXPIRED"
                elif result.get("status") == "PASS":
                    acct.last_login_status = "OK"
                elif result.get("error_code") in ("BAD_CREDENTIALS", "CAPTCHA", "LOGIN_BLOCKED"):
                    acct.last_login_status = result.get("error_code")
                    # Never rotate proxy on these
                    append_live_log(run, f"No proxy rotate on {result.get('error_code')} (policy)")

        # Network retry policy (only network codes)
        if (not mock) and may_auto_switch_network(result.get("actual") or ""):
            direct = db.query(NetworkProfile).filter(NetworkProfile.mode == "direct").first()
            if direct and network and network.id != direct.id:
                run.network_profile_id = direct.id
                network = direct
                proxy = None
                append_live_log(run, f"Auto-switched Network Profile to Direct due to {result.get('actual')}")
        elif forbid_proxy_rotate_on(result.get("actual") or ""):
            append_live_log(run, f"No proxy rotate on {result.get('actual')} (policy)")

        tr = TestResult(
            run_id=run.id,
            case_id=(task.key if task else "smoke"),
            case_name=(task.name if task else "Smoke"),
            expected=result.get("expected") or "TARGET_PAGE_READY",
            actual=result.get("actual") or "UNKNOWN",
            status=result.get("status") or "ERROR",
            duration_ms=result.get("duration_ms") or 0,
            steps=result.get("steps") or [],
            screenshot_paths=result.get("screenshot_paths") or [],
            account_email=email,
            network_profile=network.name if network else None,
            error_message=result.get("error_message"),
            pan_masked=None,
        )
        # Attach trace path into steps meta
        if result.get("trace_path"):
            steps = list(tr.steps or [])
            steps.append({"step": "trace", "ok": True, "path": result["trace_path"]})
            tr.steps = steps

        db.add(tr)
        run.progress_done = (run.progress_done or 0) + 1
        st = result.get("status")
        if st == "PASS":
            # Never count mock as live PASS without marking
            if result.get("is_mock") or mock:
                append_live_log(run, f"{email} → MOCK PASS (not live)")
            else:
                run.pass_count = (run.pass_count or 0) + 1
                append_live_log(run, f"{email} → 成功 PASS")
            if result.get("is_mock") or mock:
                run.pass_count = (run.pass_count or 0) + 1  # still count but flagged is_mock on run
        elif st == "FAIL":
            run.fail_count = (run.fail_count or 0) + 1
            append_live_log(run, f"{email} → 失败 FAIL")
        else:
            run.error_count = (run.error_count or 0) + 1
            run.error_code = result.get("error_code") or run.error_code
            append_live_log(run, f"{email} → 异常 ERROR ({result.get('error_code')})")
        db.commit()
        await asyncio.sleep(0.2)

    run.status = "COMPLETED"
    run.finished_at = datetime.now(timezone.utc)
    run.current_case_id = None
    set_run_step(run, "Completed")
    append_live_log(run, "Completed")
    db.commit()


async def process_run(db, run: TestRun, settings_obj: RunnerSettings) -> None:
    env = db.get(Environment, run.environment_id)
    if not env:
        run.status = "FAILED"
        append_live_log(run, "Environment missing")
        db.commit()
        return

    mappings = {m.key: m for m in db.query(PageMapping).all()}
    steps = db.query(WorkflowStep).order_by(WorkflowStep.sort_order).all()
    payrails = db.query(PayrailsConfig).first() or PayrailsConfig()
    network = db.get(NetworkProfile, run.network_profile_id) if run.network_profile_id else (
        db.query(NetworkProfile).filter(NetworkProfile.is_default == True).first()  # noqa
    )
    proxy = None
    if network and network.proxy_id:
        proxy = db.get(Socks5Proxy, network.proxy_id)

    account = None
    if run.account_id:
        account = db.get(QAAccount, run.account_id)
    elif getattr(run, "account_ids", None):
        account = db.get(QAAccount, run.account_ids[0]) if run.account_ids else None
    if not account:
        account = db.query(QAAccount).filter(QAAccount.status == "READY").first()

    settings = get_settings()
    mock = is_mock_mode()
    # Admin explicit mock via run name / meta
    if (run.name or "").startswith("[MOCK]") or (run.run_mode or "") == "mock":
        mock = True
    shot_root = Path(settings.screenshot_dir) / f"run-{run.id}"
    shot_root.mkdir(parents=True, exist_ok=True)
    trace_root = Path(settings.log_dir) / "traces" / f"run-{run.id}"
    trace_root.mkdir(parents=True, exist_ok=True)

    task = db.get(TaskPreset, run.task_preset_id) if getattr(run, "task_preset_id", None) else None
    run_mode = (run.run_mode or (task.task_type if task else "workflow") or "workflow")
    run.is_mock = mock

    run.status = "RUNNING"
    run.started_at = run.started_at or datetime.now(timezone.utc)
    append_live_log(run, f"Worker started mode={'MOCK' if mock else 'LIVE'} run_mode={run_mode}")
    if mock:
        append_live_log(run, "MOCK MODE — results are simulated, not live Chromium PASS")
    db.commit()

    # ── Quick-run / smoke / local_fixture path ─────────
    if run_mode in ("smoke", "local_fixture") or (task and task.task_type in ("smoke", "local_fixture")):
        await process_smoke_run(db, run, settings_obj, env, account, network, proxy, task, mock, shot_root, trace_root)
        return

    cases_done = 0
    case_list = list(run.case_ids or [])
    if not case_list and run_mode == "payment_fill":
        append_live_log(run, "No test cases for payment_fill — mark ERROR")
        run.status = "FAILED"
        run.error_code = "ACCOUNT_NOT_READY"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    for case_id in case_list:
        db.refresh(run)
        if run.status == "STOPPING":
            run.status = "STOPPED"
            append_live_log(run, "Stopped by admin")
            db.commit()
            return
        if run.status == "PAUSED":
            append_live_log(run, "Paused")
            db.commit()
            return

        case = db.query(TestCase).filter(TestCase.case_id == case_id).first()
        if not case:
            append_live_log(run, f"Case {case_id} not found — skip")
            continue

        # Account cooldown / switch
        if account and account.status == "COOLDOWN":
            if account.cooldown_until and account.cooldown_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                account = db.query(QAAccount).filter(QAAccount.status == "READY", QAAccount.id != account.id).first()
            else:
                account.status = "READY"
                account.consecutive_failures = 0

        run.current_case_id = case_id
        append_live_log(run, f"Running {case_id}")
        db.commit()

        if mock:
            result = await mock_run_case(case, env, payrails, mappings, steps, shot_root)
            result["is_mock"] = True
        else:
            ok, reason = live_testing_allowed(env)
            if not ok:
                # 1.3.0: NEVER force mock — emit ERROR code
                code = reason if reason in (LIVE_TESTING_DISABLED, ENVIRONMENT_NOT_ALLOWED) else LIVE_TESTING_DISABLED
                append_live_log(run, f"ERROR {code}: {message_zh(code)} ({reason})")
                result = {
                    "expected": case.expected_result, "actual": code, "status": "ERROR",
                    "duration_ms": 0, "steps": [{"step": "policy", "ok": False, "msg": reason}],
                    "screenshot_paths": [], "error_message": message_zh(code),
                    "pan_masked": case.pan_masked, "error_code": code, "is_mock": False,
                }
                run.error_code = code
            else:
                # Re-check allowlist before live payment
                try:
                    assert_navigation_allowed(env.base_url, env.allowed_domains or [])
                except PermissionError as e:
                    result = {
                        "expected": case.expected_result, "actual": "ALLOWLIST_REFUSED", "status": "ERROR",
                        "duration_ms": 0, "steps": [], "screenshot_paths": [],
                        "error_message": str(e), "pan_masked": case.pan_masked,
                        "error_code": "ALLOWLIST_REFUSED", "is_mock": False,
                    }
                else:
                    result = await live_run_case(
                        case, env, account, network, proxy, payrails, mappings, steps,
                        shot_root, settings_obj.timeout_sec,
                    )

        # Safety: never rotate proxy on decline/3DS/invalid
        if forbid_proxy_rotate_on(result["actual"]):
            append_live_log(run, f"No proxy rotate on {result['actual']} (policy)")
        elif may_auto_switch_network(result["actual"]):
            # Switch to Direct or next profile — new context next case
            direct = db.query(NetworkProfile).filter(NetworkProfile.mode == "direct").first()
            if direct and network and network.id != direct.id:
                run.network_profile_id = direct.id
                network = direct
                proxy = None
                append_live_log(run, f"Auto-switched Network Profile to Direct due to {result['actual']}")

        # Account failure tracking
        if account and result["status"] != "PASS":
            account.consecutive_failures = (account.consecutive_failures or 0) + 1
            if account.consecutive_failures >= settings_obj.account_failure_threshold:
                account.status = "COOLDOWN"
                account.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=settings_obj.account_cooldown_sec)
                append_live_log(run, f"Account {account.email} cooldown")
                account = db.query(QAAccount).filter(QAAccount.status == "READY").first()
        elif account:
            account.consecutive_failures = 0

        tr = TestResult(
            run_id=run.id,
            case_id=case.case_id,
            case_name=case.name,
            expected=result["expected"],
            actual=result["actual"],
            status=result["status"],
            duration_ms=result["duration_ms"],
            steps=result["steps"],
            screenshot_paths=result["screenshot_paths"],
            account_email=account.email if account else None,
            network_profile=network.name if network else None,
            error_message=result.get("error_message"),
            pan_masked=result.get("pan_masked"),
        )
        db.add(tr)
        run.progress_done = (run.progress_done or 0) + 1
        if result["status"] == "PASS":
            run.pass_count = (run.pass_count or 0) + 1
        elif result["status"] == "FAIL":
            run.fail_count = (run.fail_count or 0) + 1
        else:
            run.error_count = (run.error_count or 0) + 1
        append_live_log(run, f"{case_id} → {result['status']} ({result['expected']} vs {result['actual']})")
        db.commit()
        cases_done += 1

        # Restart browser every N (tracked via log; live mode recreates browser each case already)
        if settings_obj.restart_browser_every_n and cases_done % settings_obj.restart_browser_every_n == 0:
            append_live_log(run, "Browser restart checkpoint")
            db.commit()

        await asyncio.sleep(settings_obj.interval_sec)

    run.status = "COMPLETED"
    run.finished_at = datetime.now(timezone.utc)
    run.current_case_id = None
    append_live_log(run, "Completed")
    db.commit()


async def process_session_actions(db) -> None:
    sessions = db.query(BrowserSession).all()
    now = datetime.now(timezone.utc)
    for s in sessions:
        meta = s.meta or {}
        action = meta.get("pending_action")
        if not action:
            continue
        s.last_action = action
        s.last_activity = now
        s.last_heartbeat = now
        s.worker_id = WORKER_ID
        if action == "open":
            s.status = "READY"
            s.browser_state = "ready"
            s.context_state = "fresh"
        elif action == "close":
            s.status = "CLOSED"
            s.browser_state = "none"
            s.context_state = "none"
            s.worker_id = None
        elif action == "restart_browser":
            s.status = "READY"
            s.browser_state = "ready"
            s.context_state = "fresh"
        elif action == "restart_page":
            s.status = "READY"
            s.context_state = "active"
        elif action == "clear_cookies":
            s.status = "READY"
            s.context_state = "fresh"
        elif action == "re_login":
            s.status = "READY"
            s.context_state = "active"
        elif action == "switch_account":
            s.status = "READY"
        elif action == "switch_network":
            meta["needs_new_context"] = True
            s.context_state = "needs_new"
            s.status = "READY"
        meta.pop("pending_action", None)
        s.meta = meta
        db.commit()


async def loop() -> None:
    ensure_data_dirs()
    Base.metadata.create_all(bind=engine)
    try:
        from app.core.database import ensure_schema
        ensure_schema()
    except Exception:
        logger.exception("ensure_schema failed")
    db = SessionLocal()
    try:
        seed_all(db)
        mark_sessions_stale_on_startup(db)
    finally:
        db.close()

    settings = get_settings()
    poll = float(os.environ.get("WORKER_POLL_INTERVAL_SEC", settings.worker_poll_interval_sec))
    mock_mode = is_mock_mode()
    live_flag = os.environ.get("LIVE_TESTING_ENABLED", str(settings.live_testing_enabled))
    logger.info(
        "Worker started poll=%.1fs mock=%s live_testing=%s db=%s worker_id=%s",
        poll, mock_mode, live_flag, settings.database_url, WORKER_ID,
    )

    while True:
        db = SessionLocal()
        try:
            heartbeat(db)
            await process_session_actions(db)
            rs = db.query(RunnerSettings).first() or RunnerSettings()
            # Faster interval in mock CI
            if mock_mode and rs.interval_sec > 0.5:
                rs.interval_sec = 0.2
            run = (
                db.query(TestRun)
                .filter(TestRun.status == "QUEUED")
                .order_by(TestRun.id)
                .first()
            )
            if run:
                logger.info("Picked run id=%s", run.id)
                await process_run(db, run, rs)
        except Exception:
            logger.exception("Worker loop error")
            try:
                db.rollback()
                db.add(AppLog(level="ERROR", source="worker", message="loop error", meta={}))
                db.commit()
            except Exception:
                pass
        finally:
            db.close()
        await asyncio.sleep(poll)


def main():
    asyncio.run(loop())


if __name__ == "__main__":
    main()
