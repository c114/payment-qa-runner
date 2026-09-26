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
    QAAccount, RunnerSettings, Socks5Proxy, SystemSettings, TestCase, TestResult, TestRun,
    WorkflowStep,
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


def live_testing_allowed(env: Environment) -> tuple[bool, str]:
    """Refuse live browser payment unless LIVE_TESTING_ENABLED and env is sandbox|staging|internal + allowlist."""
    settings = get_settings()
    flag = os.environ.get("LIVE_TESTING_ENABLED", str(settings.live_testing_enabled)).lower() in ("1", "true", "yes")
    if not flag:
        return False, "LIVE_TESTING_ENABLED is false — refusing live browser payment runs"
    if (env.env_type or "").lower() not in ("sandbox", "staging", "internal"):
        return False, f"env_type={env.env_type} not sandbox/staging/internal"
    if not (env.allowed_domains or []):
        return False, "allowed_domains empty — fail closed"
    if not is_url_allowed(env.base_url, env.allowed_domains or []):
        return False, "base_url outside allowed_domains"
    return True, "ok"


def append_live_log(run: TestRun, msg: str) -> None:
    log = list(run.live_log or [])
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": msg})
    run.live_log = log[-200:]


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

    account = db.get(QAAccount, run.account_id) if run.account_id else (
        db.query(QAAccount).filter(QAAccount.status == "READY").first()
    )

    settings = get_settings()
    mock = bool(int(os.environ.get("PLAYWRIGHT_MOCK", settings.playwright_mock or 0)))
    shot_root = Path(settings.screenshot_dir) / f"run-{run.id}"
    shot_root.mkdir(parents=True, exist_ok=True)

    run.status = "RUNNING"
    run.started_at = run.started_at or datetime.now(timezone.utc)
    append_live_log(run, f"Worker started (mock={mock})")
    db.commit()

    cases_done = 0
    for case_id in list(run.case_ids or []):
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
        else:
            ok, reason = live_testing_allowed(env)
            if not ok:
                append_live_log(run, f"Live testing refused: {reason} — force mock")
                result = await mock_run_case(case, env, payrails, mappings, steps, shot_root)
                result["error_message"] = (result.get("error_message") or "") + f" | live refused: {reason}"
            else:
                # Re-check allowlist before live payment
                assert_navigation_allowed(env.base_url, env.allowed_domains or [])
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
    mock_mode = bool(int(os.environ.get("PLAYWRIGHT_MOCK", settings.playwright_mock or 0)))
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
