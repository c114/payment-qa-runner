"""Payment Test Runner 2.0.0 worker — LIVE Playwright only, no Mock PASS fallback."""
from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure backend on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.core.config import ensure_data_dirs, get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import decrypt_secret
from app.models.models import Account, Artifact, NetworkProfile, Run, RunItem, TestData
from app.services.result_codes import bucket, never_unknown_as_success
from worker.flows.preply_smoke import run_preply_smoke
from worker.flows.sandbox_bind import run_sandbox_bind

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker %(message)s")
logger = logging.getLogger("worker")


def utcnow():
    return datetime.now(timezone.utc)


def touch_heartbeat():
    s = get_settings()
    path = s.worker_heartbeat_file
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        Path(path).write_text(str(time.time()))
    except OSError as e:
        logger.warning("heartbeat: %s", e)


def append_log(db: Session, run: Run, msg: str):
    log = list(run.live_log or [])
    log.append({"ts": utcnow().isoformat(), "msg": msg})
    if len(log) > 500:
        log = log[-500:]
    run.live_log = log
    db.commit()


def proxy_from_network(db: Session, run: Run) -> Optional[dict]:
    snap = run.network_snapshot or {}
    proto = (snap.get("protocol") or "direct").lower()
    if proto == "direct":
        return None
    host = snap.get("host")
    port = snap.get("port")
    if not host or not port:
        return None
    username = snap.get("username")
    password = None
    if run.network_id:
        n = db.query(NetworkProfile).filter(NetworkProfile.id == run.network_id).first()
        if n and n.password_enc:
            password = decrypt_secret(n.password_enc)
    server = f"{proto}://{host}:{port}"
    cfg: dict[str, Any] = {"server": server}
    if username:
        cfg["username"] = username
    if password:
        cfg["password"] = password
    return cfg


def save_artifact(db: Session, run_id: int, item_id: int, kind: str, path: str, meta: dict | None = None):
    db.add(Artifact(run_id=run_id, run_item_id=item_id, kind=kind, path=path, meta=meta or {}))
    db.commit()


def finish_item(db: Session, run: Run, item: RunItem, account: Optional[Account], code: str, reason: str, steps: list, t0: float):
    code = never_unknown_as_success(code)
    b = bucket(code)
    item.result_code = code
    item.reason = reason
    item.steps = steps
    item.duration_ms = (time.monotonic() - t0) * 1000
    item.finished_at = utcnow()
    if code == "CANCELLED":
        item.status = "CANCELLED"
        run.cancelled_count = (run.cancelled_count or 0) + 1
    elif b == "SUCCESS":
        item.status = "SUCCESS"
        run.success_count = (run.success_count or 0) + 1
    elif b == "FAIL":
        item.status = "FAIL"
        run.fail_count = (run.fail_count or 0) + 1
    else:
        item.status = "ERROR"
        run.error_count = (run.error_count or 0) + 1
    item.state = "COMPLETED" if b == "SUCCESS" else ("CANCELLED" if code == "CANCELLED" else "ERROR")
    run.progress_done = (run.progress_done or 0) + 1
    if account:
        account.last_result = code
        account.last_used_at = utcnow()
    db.commit()


def process_item(db: Session, run: Run, item: RunItem, browser) -> None:
    s = get_settings()
    t0 = time.monotonic()
    steps: list[dict] = []
    account = db.query(Account).filter(Account.id == item.account_id).first() if item.account_id else None
    td = db.query(TestData).filter(TestData.id == item.test_data_id).first() if item.test_data_id else None

    item.status = "RUNNING"
    item.started_at = utcnow()
    item.state = "STARTING_BROWSER"
    run.current_account = item.account_email
    run.current_step = "STARTING_BROWSER"
    db.commit()

    def stop_check() -> bool:
        db.refresh(run)
        return bool(run.stop_requested)

    def on_step(state: str, msg: str):
        steps.append({"state": state, "msg": msg, "ts": utcnow().isoformat()})
        item.state = state
        run.current_step = state
        append_log(db, run, f"[{item.account_email}] {state}: {msg}")

    if not account:
        finish_item(db, run, item, None, "ERROR/BAD_CREDENTIALS", "account missing", steps, t0)
        return

    password = decrypt_secret(account.password_enc)
    task = run.task_snapshot or {}
    allow_fill = bool(task.get("allow_card_fill"))
    env_type = task.get("env_type") or ""
    # HARD safety: Production never fill
    if env_type == "Production":
        allow_fill = False

    pan = expiry = cvc = ""
    if allow_fill:
        if not td:
            finish_item(db, run, item, account, "FAIL/INVALID_DATA", "missing test data", steps, t0)
            return
        pan = decrypt_secret(td.pan_enc)
        expiry = td.expiry
        cvc = decrypt_secret(td.cvc_enc)

    proxy = proxy_from_network(db, run)
    context_kwargs: dict[str, Any] = {}
    if proxy:
        context_kwargs["proxy"] = proxy

    # Session reuse
    storage = None
    if account.session_status == "VALID" and account.session_path and os.path.isfile(account.session_path):
        storage = account.session_path
        context_kwargs["storage_state"] = storage

    context = browser.new_context(**context_kwargs)
    # Trace
    trace_path = os.path.join(s.trace_dir, f"run{run.id}_item{item.id}.zip")
    os.makedirs(s.trace_dir, exist_ok=True)
    context.tracing.start(screenshots=True, snapshots=True)

    page = context.new_page()
    result: dict[str, Any] = {"code": "ERROR/UNKNOWN_RESULT", "reason": "not executed"}

    try:
        if allow_fill:
            result = run_sandbox_bind(
                page,
                base_url=task.get("base_url") or "",
                login_url=task.get("login_url") or "",
                target_url=task.get("target_url") or "",
                email=account.email,
                password=password,
                pan=pan,
                expiry=expiry,
                cvc=cvc,
                on_step=on_step,
                stop_check=stop_check,
            )
            if td:
                td.used_count = (td.used_count or 0) + 1
                td.last_used_at = utcnow()
                td.status = "USED"
                db.commit()
        else:
            result = run_preply_smoke(
                page,
                target_url=task.get("target_url") or "",
                login_url=task.get("login_url") or "",
                email=account.email,
                password=password,
                open_add_card=bool((task.get("config") or {}).get("open_add_card_modal", True)),
                on_step=on_step,
                stop_check=stop_check,
            )

        # Screenshot only after stable terminal state (not mid-nav)
        code = never_unknown_as_success(result.get("code"))
        shot = os.path.join(s.screenshot_dir, f"run{run.id}_item{item.id}.png")
        os.makedirs(s.screenshot_dir, exist_ok=True)
        try:
            page.wait_for_timeout(300)
            page.screenshot(path=shot, full_page=True)
            save_artifact(db, run.id, item.id, "screenshot", shot, {"result": code})
        except Exception as e:
            logger.warning("screenshot failed: %s", e)

        # Persist session if auth looked OK
        if code.startswith("SUCCESS") or item.state in ("AUTH_SUCCESS", "TARGET_READY", "COMPLETED", "FORM_OPEN"):
            sess_path = os.path.join(s.session_dir, f"account_{account.id}.json")
            os.makedirs(s.session_dir, exist_ok=True)
            try:
                context.storage_state(path=sess_path)
                account.session_status = "VALID"
                account.session_path = sess_path
                account.session_updated_at = utcnow()
                db.commit()
            except Exception:
                pass

        finish_item(db, run, item, account, code, result.get("reason") or "", steps, t0)

    except Exception as e:
        logger.error("item error: %s\n%s", e, traceback.format_exc())
        finish_item(db, run, item, account, "ERROR/BROWSER_ERROR", str(e)[:300], steps, t0)
    finally:
        try:
            context.tracing.stop(path=trace_path)
            save_artifact(db, run.id, item.id, "trace", trace_path, {})
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass
        # Wipe CVC from memory refs
        cvc = ""
        pan = ""


def process_run(db: Session, run: Run) -> None:
    s = get_settings()
    run.status = "RUNNING"
    run.started_at = utcnow()
    run.mode = "LIVE"
    append_log(db, run, "Worker picked up run (LIVE)")

    # PLAYWRIGHT_MOCK must never force PASS
    if s.playwright_mock:
        append_log(db, run, "WARNING: PLAYWRIGHT_MOCK=1 ignored — 2.0 always LIVE")

    from playwright.sync_api import sync_playwright

    items = (
        db.query(RunItem)
        .filter(RunItem.run_id == run.id, RunItem.status == "WAITING")
        .order_by(RunItem.id)
        .all()
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for item in items:
                db.refresh(run)
                if run.stop_requested:
                    # Cancel remaining
                    remaining = (
                        db.query(RunItem)
                        .filter(RunItem.run_id == run.id, RunItem.status == "WAITING")
                        .all()
                    )
                    for rem in remaining:
                        rem.status = "CANCELLED"
                        rem.result_code = "CANCELLED"
                        rem.reason = "stopped by user"
                        rem.state = "CANCELLED"
                        rem.finished_at = utcnow()
                        run.cancelled_count = (run.cancelled_count or 0) + 1
                        run.progress_done = (run.progress_done or 0) + 1
                    db.commit()
                    append_log(db, run, "STOP: remaining items CANCELLED")
                    break
                process_item(db, run, item, browser)
        finally:
            try:
                browser.close()
            except Exception:
                pass

    db.refresh(run)
    if run.stop_requested:
        run.status = "CANCELLED"
    elif (run.error_count or 0) > 0 and (run.success_count or 0) == 0 and (run.fail_count or 0) == 0:
        run.status = "FAILED"
    else:
        run.status = "COMPLETED"
    run.finished_at = utcnow()
    run.current_step = run.status
    run.current_account = None
    append_log(db, run, f"Run finished: {run.status}")
    db.commit()


def loop():
    ensure_data_dirs()
    Base.metadata.create_all(bind=engine)
    logger.info("Worker 2.0.0 started (LIVE mode)")
    while True:
        touch_heartbeat()
        db = SessionLocal()
        try:
            run = (
                db.query(Run)
                .filter(Run.status == "QUEUED")
                .order_by(Run.id)
                .first()
            )
            if run:
                logger.info("Processing run #%s", run.id)
                process_run(db, run)
            else:
                # Also resume STOPPING with no active — mark cancelled leftovers
                stopping = db.query(Run).filter(Run.status == "STOPPING").first()
                if stopping and stopping.stop_requested:
                    # If worker crashed mid-stop, finalize
                    waiting = db.query(RunItem).filter(RunItem.run_id == stopping.id, RunItem.status == "WAITING").all()
                    for rem in waiting:
                        rem.status = "CANCELLED"
                        rem.result_code = "CANCELLED"
                        rem.state = "CANCELLED"
                        rem.finished_at = utcnow()
                        stopping.cancelled_count = (stopping.cancelled_count or 0) + 1
                    stopping.status = "CANCELLED"
                    stopping.finished_at = utcnow()
                    db.commit()
        except Exception:
            logger.error("loop error:\n%s", traceback.format_exc())
        finally:
            db.close()
        time.sleep(get_settings().worker_poll_interval_sec)


if __name__ == "__main__":
    loop()
