"""All API routes for Payment QA Runner."""
from __future__ import annotations

import csv
import io
import json
import logging
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, decrypt_secret, encrypt_secret, never_persist_cvv,
    redact_dict, verify_password, mask_pan,
)
from app.models.models import (
    AdminUser, AccountCreationSettings, AppLog, BrowserSession, Environment,
    NetworkProfile, PageMapping, PayrailsConfig, QAAccount, RunnerSettings,
    Socks5Proxy, SystemSettings, TestCase, TestResult, TestRun, WorkflowStep,
)
from app.schemas.schemas import *
from app.services.account_creation import can_enable_account_creation
from app.services.allowlist import assert_navigation_allowed, is_url_allowed, validate_environment_url
from app.services.comparison import compare_expected_actual
from app.services.socks5_probe import probe_socks5, parse_proxy_test_target
from app.services.parsers import (
    parse_qa_accounts, parse_socks5, parse_test_cases,
    parse_page_mappings_json, parse_environment_json, TEMPLATES,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _log(db: Session, level: str, source: str, message: str, meta: dict | None = None):
    db.add(AppLog(level=level, source=source, message=message, meta=redact_dict(meta or {})))
    db.commit()


# ── Auth ──────────────────────────────────────────────
# In-memory login rate limit: 5 attempts / minute per IP+email
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_LIMIT = 5
_LOGIN_WINDOW = 60.0


def _rate_limit_login(ip: str, email: str) -> None:
    key = f"{ip}|{(email or '').lower()}"
    now = time.time()
    bucket = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < _LOGIN_WINDOW]
    if len(bucket) >= _LOGIN_LIMIT:
        _LOGIN_ATTEMPTS[key] = bucket
        raise HTTPException(429, "Too many login attempts — retry in a minute")
    bucket.append(now)
    _LOGIN_ATTEMPTS[key] = bucket


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _rate_limit_login(ip, body.email)
    user = db.query(AdminUser).filter(AdminUser.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenOut(access_token=create_access_token(user.email))


@router.get("/auth/me")
def me(admin: AdminUser = Depends(get_current_admin)):
    return {"email": admin.email, "id": admin.id}


# ── Health ────────────────────────────────────────────
def _component(status: str, last_seen: Optional[str] = None) -> dict:
    return {"status": status, "last_seen": last_seen or datetime.now(timezone.utc).isoformat()}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    db_ok = False
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    worker_status = "down"
    worker_last = None
    try:
        hb = db.query(SystemSettings).filter(SystemSettings.key == "worker_heartbeat").first()
        if hb and hb.value:
            ts = hb.value.get("ts")
            if ts:
                age = time.time() - float(ts)
                worker_last = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
                worker_status = "ok" if age < settings.session_heartbeat_stale_sec else "down"
    except Exception:
        worker_status = "down"

    # browser_worker: based on open/ready session heartbeats
    stale_sec = settings.session_heartbeat_stale_sec
    browser_status = "idle"
    browser_last = None
    try:
        sessions = db.query(BrowserSession).filter(
            BrowserSession.status.in_(["OPEN", "READY", "RUNNING", "STALE"])
        ).all()
        if sessions:
            fresh = False
            for s in sessions:
                if s.last_heartbeat:
                    hb_ts = s.last_heartbeat
                    if hb_ts.tzinfo is None:
                        hb_ts = hb_ts.replace(tzinfo=timezone.utc)
                    age = (now - hb_ts).total_seconds()
                    browser_last = hb_ts.isoformat()
                    if age <= stale_sec and s.status in ("OPEN", "READY", "RUNNING"):
                        fresh = True
                        break
            browser_status = "ok" if fresh else ("down" if worker_status == "down" else "idle")
    except Exception:
        browser_status = "idle"

    return {
        "backend": _component("ok", now_iso),
        "database": _component("ok" if db_ok else "down", now_iso),
        "worker": _component(worker_status, worker_last or now_iso),
        "browser_worker": _component(browser_status, browser_last or now_iso),
        "mock": bool(settings.playwright_mock),
        "live_testing_enabled": bool(settings.live_testing_enabled),
        "version": "1.2.0",
        "time": now_iso,
    }


# ── Dashboard ─────────────────────────────────────────
@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    running = db.query(TestRun).filter(TestRun.status.in_(["RUNNING", "PAUSED", "QUEUED"])).count()
    total_results = db.query(TestResult).count()
    passes = db.query(TestResult).filter(TestResult.status == "PASS").count()
    fails = db.query(TestResult).filter(TestResult.status == "FAIL").count()
    errors = db.query(TestResult).filter(TestResult.status == "ERROR").count()
    accounts_ready = db.query(QAAccount).filter(QAAccount.status == "READY").count()
    proxies_online = db.query(Socks5Proxy).filter(Socks5Proxy.status == "ONLINE").count()
    envs = db.query(Environment).filter(Environment.is_active == True).count()  # noqa: E712
    cases = db.query(TestCase).filter(TestCase.is_active == True).count()  # noqa: E712
    # Wizard checklist 1-11
    wizard = [
        {"step": 1, "key": "admin", "done": db.query(AdminUser).count() > 0, "label_zh": "管理员已创建"},
        {"step": 2, "key": "environment", "done": envs > 0, "label_zh": "已配置沙箱环境"},
        {"step": 3, "key": "page_mapping", "done": db.query(PageMapping).filter(PageMapping.selector != "").count() > 0, "label_zh": "页面映射已填写"},
        {"step": 4, "key": "workflow", "done": db.query(WorkflowStep).count() > 0, "label_zh": "工作流步骤就绪"},
        {"step": 5, "key": "accounts", "done": accounts_ready > 0, "label_zh": "QA 账号就绪"},
        {"step": 6, "key": "network", "done": db.query(NetworkProfile).count() > 0, "label_zh": "网络配置就绪"},
        {"step": 7, "key": "cases", "done": cases > 0, "label_zh": "测试用例已导入"},
        {"step": 8, "key": "payrails", "done": bool((db.query(PayrailsConfig).first() or PayrailsConfig()).sandbox_base_url or True), "label_zh": "Payrails 面板可配置"},
        {"step": 9, "key": "runner", "done": db.query(RunnerSettings).count() > 0, "label_zh": "Runner 设置就绪"},
        {"step": 10, "key": "session", "done": True, "label_zh": "浏览器会话可用"},
        {"step": 11, "key": "run", "done": db.query(TestRun).count() > 0, "label_zh": "已创建过测试运行"},
    ]
    active_run = db.query(TestRun).filter(TestRun.status.in_(["RUNNING", "PAUSED", "QUEUED", "STOPPING"])).order_by(TestRun.id.desc()).first()
    return {
        "running_runs": running,
        "total_results": total_results,
        "pass_count": passes,
        "fail_count": fails,
        "error_count": errors,
        "accounts_ready": accounts_ready,
        "proxies_online": proxies_online,
        "environments": envs,
        "cases": cases,
        "wizard": wizard,
        "active_run": TestRunOut.model_validate(active_run).model_dump() if active_run else None,
    }


# ── Environments ──────────────────────────────────────
@router.get("/environments", response_model=List[EnvironmentOut])
def list_envs(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(Environment).order_by(Environment.id).all()


@router.post("/environments", response_model=EnvironmentOut)
def create_env(body: EnvironmentIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if body.env_type not in ("sandbox", "staging", "internal"):
        raise HTTPException(400, "env_type must be sandbox|staging|internal")
    warnings = validate_environment_url(body.base_url, body.env_type)
    # Auto-fill allowed_domains from base_url host if empty
    domains = list(body.allowed_domains)
    if not domains:
        from app.services.allowlist import extract_host
        h = extract_host(body.base_url)
        if h:
            domains = [h]
    env = Environment(**body.model_dump() | {"allowed_domains": domains})
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.put("/environments/{env_id}", response_model=EnvironmentOut)
def update_env(env_id: int, body: EnvironmentIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(env, k, v)
    db.commit()
    db.refresh(env)
    return env


@router.delete("/environments/{env_id}")
def delete_env(env_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404)
    db.delete(env)
    db.commit()
    return {"message": "deleted"}


@router.post("/environments/{env_id}/test")
def test_env(env_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404)
    status_str = "FAIL"
    detail = ""
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(env.base_url)
            status_str = "OK" if r.status_code < 500 else "FAIL"
            detail = f"HTTP {r.status_code}"
    except Exception as e:
        status_str = "FAIL"
        detail = str(e)
    env.last_test_status = status_str
    env.last_test_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": status_str, "detail": detail, "warnings": validate_environment_url(env.base_url, env.env_type)}


# ── Page Mapping ──────────────────────────────────────
@router.get("/page-mappings", response_model=List[PageMappingOut])
def list_mappings(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(PageMapping).order_by(PageMapping.sort_order).all()


@router.put("/page-mappings/{mid}", response_model=PageMappingOut)
def update_mapping(mid: int, body: PageMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = db.get(PageMapping, mid)
    if not m:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.post("/page-mappings", response_model=PageMappingOut)
def create_mapping(body: PageMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = PageMapping(**body.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.post("/page-mappings/test-selector")
def test_selector(body: dict, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """Locate-only Playwright test — no payment. Uses mock if PLAYWRIGHT_MOCK=1.
    Result codes: FOUND | NOT_FOUND | TIMEOUT | IFRAME_ERROR
    """
    settings = get_settings()
    env_id = body.get("environment_id")
    selector = body.get("selector", "")
    selector_type = body.get("selector_type", "css")
    iframe_selector = body.get("iframe_selector")
    if settings.playwright_mock:
        return {
            "ok": True, "mock": True, "found": True, "count": 1,
            "result": "FOUND", "message": "Mock: selector would be tested",
        }
    env = db.get(Environment, env_id) if env_id else None
    if not env:
        raise HTTPException(400, "environment_id required for live selector test")
    try:
        from app.services.selector_test import test_selector_live
        r = test_selector_live(env, selector, selector_type, iframe_selector)
        found = bool(r.get("found"))
        r["result"] = "FOUND" if found else "NOT_FOUND"
        return r
    except ImportError:
        return {"ok": False, "result": "NOT_FOUND", "message": "Playwright not available in API process; use worker or mock mode"}
    except Exception as e:
        msg = str(e).lower()
        if "iframe" in msg or "frame" in msg:
            code = "IFRAME_ERROR"
        elif "timeout" in msg:
            code = "TIMEOUT"
        else:
            code = "NOT_FOUND"
        return {"ok": False, "result": code, "message": str(e)}


# ── Workflow ──────────────────────────────────────────
@router.get("/workflow-steps", response_model=List[WorkflowStepOut])
def list_steps(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(WorkflowStep).order_by(WorkflowStep.sort_order).all()


@router.put("/workflow-steps/{sid}", response_model=WorkflowStepOut)
def update_step(sid: int, body: WorkflowStepIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    s = db.get(WorkflowStep, sid)
    if not s:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


# ── QA Accounts ───────────────────────────────────────
@router.get("/accounts", response_model=List[QAAccountOut])
def list_accounts(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(QAAccount).order_by(QAAccount.id).all()


@router.post("/accounts", response_model=QAAccountOut)
def create_account(body: QAAccountIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if db.query(QAAccount).filter(QAAccount.email == body.email).first():
        raise HTTPException(400, "email exists")
    acc = QAAccount(
        email=body.email,
        password_enc=encrypt_secret(body.password),
        display_name=body.display_name,
        notes=body.notes,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/accounts/{aid}")
def delete_account(aid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    a = db.get(QAAccount, aid)
    if not a:
        raise HTTPException(404)
    db.delete(a)
    db.commit()
    return {"message": "deleted"}


@router.post("/accounts/import")
def import_accounts(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    parsed = parse_qa_accounts(body.text)
    created = 0
    for item in parsed.items:
        if db.query(QAAccount).filter(QAAccount.email == item["email"]).first():
            continue
        db.add(QAAccount(
            email=item["email"],
            password_enc=encrypt_secret(item["password"]),
            display_name=item.get("display_name"),
            notes=item.get("notes") or item.get("tag"),
        ))
        created += 1
    db.commit()
    return {"created": created, "errors": parsed.errors, "parsed": len(parsed.items)}


@router.post("/accounts/{aid}/test-login")
def test_login(aid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    a = db.get(QAAccount, aid)
    if not a:
        raise HTTPException(404)
    # Does not run real login here unless worker handles; mark as checked
    pwd = decrypt_secret(a.password_enc)
    a.last_login_status = "PASSWORD_DECRYPT_OK" if pwd else "DECRYPT_FAIL"
    db.commit()
    return {"status": a.last_login_status, "message": "Password decrypt check only; full login via Browser Session"}


@router.get("/account-creation")
def get_acct_creation(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    s = db.query(AccountCreationSettings).first()
    return AccountCreationIn(enabled=s.enabled, test_email_domain=s.test_email_domain, name_prefix=s.name_prefix) if s else AccountCreationIn()


@router.put("/account-creation")
def put_acct_creation(body: AccountCreationIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    ok, msg = can_enable_account_creation(body.enabled, body.test_email_domain)
    if not ok:
        raise HTTPException(400, msg)
    s = db.query(AccountCreationSettings).first()
    if not s:
        s = AccountCreationSettings()
        db.add(s)
    s.enabled = body.enabled
    s.test_email_domain = body.test_email_domain
    s.name_prefix = body.name_prefix
    db.commit()
    return {"message": "ok", "detail": msg}


# ── SOCKS5 ────────────────────────────────────────────
@router.get("/proxies", response_model=List[Socks5Out])
def list_proxies(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(Socks5Proxy).order_by(Socks5Proxy.id).all()


@router.post("/proxies", response_model=Socks5Out)
def create_proxy(body: Socks5In, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    p = Socks5Proxy(
        host=body.host, port=body.port, username=body.username,
        password_enc=encrypt_secret(body.password) if body.password else None,
        label=body.label, is_active=body.is_active,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/proxies/{pid}")
def delete_proxy(pid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    p = db.get(Socks5Proxy, pid)
    if not p:
        raise HTTPException(404)
    db.delete(p)
    db.commit()
    return {"message": "deleted"}


@router.post("/proxies/import")
def import_proxies(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    parsed = parse_socks5(body.text)
    created = 0
    for item in parsed.items:
        exists = db.query(Socks5Proxy).filter(
            Socks5Proxy.host == item["host"], Socks5Proxy.port == item["port"],
            Socks5Proxy.username == item.get("username"),
        ).first()
        if exists:
            continue
        db.add(Socks5Proxy(
            host=item["host"], port=item["port"], username=item.get("username"),
            password_enc=encrypt_secret(item["password"]) if item.get("password") else None,
        ))
        created += 1
    db.commit()
    return {"created": created, "errors": parsed.errors, "parsed": len(parsed.items)}


@router.post("/proxies/{pid}/test")
def test_proxy(pid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    p = db.get(Socks5Proxy, pid)
    if not p:
        raise HTTPException(404)
    settings = get_settings()
    # Prefer admin system setting proxy_test_url, else env PROXY_TEST_URL
    sys_row = db.query(SystemSettings).filter(SystemSettings.key == "proxy_test_url").first()
    test_url = None
    if sys_row and isinstance(sys_row.value, dict):
        test_url = sys_row.value.get("url") or sys_row.value.get("proxy_test_url")
    test_url = test_url or settings.proxy_test_url
    pwd = decrypt_secret(p.password_enc) if p.password_enc else None
    result = probe_socks5(
        p.host, p.port,
        username=p.username,
        password=pwd,
        test_url=test_url,
        timeout=8.0,
        fetch_exit_ip=True,
    )
    status_str = result.status if result.status != "UNKNOWN" else "HANDSHAKE_ERROR"
    p.status = status_str
    p.latency_ms = result.latency_ms
    p.exit_ip = result.exit_ip
    p.last_tested_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": status_str,
        "latency_ms": result.latency_ms,
        "exit_ip": result.exit_ip,
        "detail": result.detail,
        "test_target": list(parse_proxy_test_target(test_url)),
    }


# ── Network Profiles ──────────────────────────────────
@router.get("/network-profiles", response_model=List[NetworkProfileOut])
def list_np(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(NetworkProfile).all()


@router.post("/network-profiles", response_model=NetworkProfileOut)
def create_np(body: NetworkProfileIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    np = NetworkProfile(**body.model_dump())
    db.add(np)
    db.commit()
    db.refresh(np)
    return np


@router.delete("/network-profiles/{nid}")
def delete_np(nid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    np = db.get(NetworkProfile, nid)
    if not np:
        raise HTTPException(404)
    if np.name == "Direct":
        raise HTTPException(400, "Cannot delete Direct profile")
    db.delete(np)
    db.commit()
    return {"message": "deleted"}


# ── Browser Sessions ──────────────────────────────────
def _effective_session_status(s: BrowserSession, stale_sec: int) -> str:
    """Never report READY/OPEN/RUNNING if worker heartbeat is stale."""
    status = s.status or "CLOSED"
    if status in ("CLOSED", "ERROR", "STALE"):
        return status
    if status in ("READY", "OPEN", "RUNNING"):
        if not s.last_heartbeat:
            return "STALE"
        hb = s.last_heartbeat
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - hb).total_seconds()
        if age > stale_sec:
            return "STALE"
    return status


@router.get("/browser-sessions", response_model=List[BrowserSessionOut])
def list_sessions(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    settings = get_settings()
    rows = db.query(BrowserSession).order_by(BrowserSession.id.desc()).all()
    out = []
    for s in rows:
        eff = _effective_session_status(s, settings.session_heartbeat_stale_sec)
        data = BrowserSessionOut.model_validate(s).model_dump()
        data["status"] = eff
        out.append(BrowserSessionOut(**data))
    return out


@router.post("/browser-sessions", response_model=BrowserSessionOut)
def create_session(body: BrowserSessionIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    s = BrowserSession(**body.model_dump(), status="CLOSED")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/browser-sessions/{sid}/action")
def session_action(sid: int, body: dict, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """Actions: open|restart_page|restart_browser|clear_cookies|re_login|switch_account|switch_network|close
    switch_network = new context (not hot-patch proxy).
    """
    s = db.get(BrowserSession, sid)
    if not s:
        raise HTTPException(404)
    action = body.get("action", "")
    allowed = {"open", "restart_page", "restart_browser", "clear_cookies", "re_login", "switch_account", "switch_network", "close"}
    if action not in allowed:
        raise HTTPException(400, f"action must be one of {allowed}")
    now = datetime.now(timezone.utc)
    if action == "switch_network":
        np_id = body.get("network_profile_id")
        if np_id:
            s.network_profile_id = np_id
        s.meta = {**(s.meta or {}), "needs_new_context": True}
        s.context_state = "needs_new"
        s.status = "READY"
    if action == "switch_account":
        acc_id = body.get("account_id")
        if acc_id:
            s.account_id = acc_id
        s.status = "READY"
    if action == "open":
        s.status = "READY"
        s.browser_state = "starting"
        s.context_state = "fresh"
    if action == "close":
        s.status = "CLOSED"
        s.browser_state = "none"
        s.context_state = "none"
        s.worker_id = None
    if action == "restart_browser":
        s.status = "READY"
        s.browser_state = "starting"
        s.context_state = "fresh"
    if action == "restart_page":
        s.status = "READY"
        s.context_state = "active"
    if action == "clear_cookies":
        s.status = "READY"
        s.context_state = "fresh"
    if action == "re_login":
        s.status = "READY"
    s.last_action = action
    s.last_activity = now
    s.meta = {**(s.meta or {}), "pending_action": action}
    db.commit()
    db.refresh(s)
    return {"message": f"queued {action}", "session": BrowserSessionOut.model_validate(s)}


# ── Test Cases ────────────────────────────────────────
@router.get("/test-cases", response_model=List[TestCaseOut])
def list_cases(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(TestCase).order_by(TestCase.id).all()


@router.post("/test-cases", response_model=TestCaseOut)
def create_case(body: TestCaseIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    data = never_persist_cvv(body.model_dump())
    if data.get("pan_masked") and "****" not in str(data["pan_masked"]):
        data["pan_masked"] = mask_pan(data["pan_masked"])
    c = TestCase(**data)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/test-cases/{cid}", response_model=TestCaseOut)
def update_case(cid: int, body: TestCaseIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = db.get(TestCase, cid)
    if not c:
        raise HTTPException(404)
    data = never_persist_cvv(body.model_dump())
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/test-cases/{cid}")
def delete_case(cid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = db.get(TestCase, cid)
    if not c:
        raise HTTPException(404)
    db.delete(c)
    db.commit()
    return {"message": "deleted"}


@router.post("/test-cases/import")
def import_cases(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    parsed = parse_test_cases(body.text, mapping=body.mapping, delimiter=body.delimiter)
    created = 0
    updated = 0
    for item in parsed.items:
        item = never_persist_cvv(item)
        existing = db.query(TestCase).filter(TestCase.case_id == item["case_id"]).first()
        if existing:
            for k, v in item.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(TestCase(**item))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "errors": parsed.errors, "parsed": len(parsed.items)}


# ── Test Runs ─────────────────────────────────────────
@router.get("/test-runs", response_model=List[TestRunOut])
def list_runs(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return db.query(TestRun).order_by(TestRun.id.desc()).limit(100).all()


@router.get("/test-runs/{rid}", response_model=TestRunOut)
def get_run(rid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    r = db.get(TestRun, rid)
    if not r:
        raise HTTPException(404)
    return r


@router.post("/test-runs", response_model=TestRunOut)
def create_run(body: TestRunCreate, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if body.run_count not in ("1", "5", "10", "50", "ALL"):
        raise HTTPException(400, "run_count must be 1|5|10|50|ALL")
    env = db.get(Environment, body.environment_id)
    if not env:
        raise HTTPException(400, "environment required")
    if not env.allowed_domains:
        raise HTTPException(400, "Environment must have allowed_domains")
    case_ids = list(body.case_ids)
    if not case_ids:
        case_ids = [c.case_id for c in db.query(TestCase).filter(TestCase.is_active == True).all()]  # noqa
    if body.run_count == "ALL":
        total = len(case_ids)
    else:
        n = int(body.run_count)
        case_ids = (case_ids * ((n // max(len(case_ids), 1)) + 1))[:n]
        total = len(case_ids)
    run = TestRun(
        name=body.name or f"Run {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        environment_id=body.environment_id,
        account_id=body.account_id,
        network_profile_id=body.network_profile_id,
        proxy_pool_ids=body.proxy_pool_ids,
        case_ids=case_ids,
        run_count=body.run_count,
        status="QUEUED",
        progress_total=total,
        live_log=[{"ts": datetime.now(timezone.utc).isoformat(), "msg": "Run created"}],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.post("/test-runs/{rid}/{action}")
def run_control(rid: int, action: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    run = db.get(TestRun, rid)
    if not run:
        raise HTTPException(404)
    action = action.upper()
    transitions = {
        "START": ("QUEUED", "PAUSED", "STOPPED"),
        "PAUSE": ("RUNNING",),
        "RESUME": ("PAUSED",),
        "STOP": ("RUNNING", "PAUSED", "QUEUED"),
    }
    if action not in transitions:
        raise HTTPException(400, "action must be START|PAUSE|RESUME|STOP")
    if run.status not in transitions[action] and not (action == "START" and run.status == "QUEUED"):
        # Allow START from QUEUED always
        if not (action == "START" and run.status in ("QUEUED", "PAUSED", "STOPPED")):
            raise HTTPException(400, f"Cannot {action} from {run.status}")
    mapping = {"START": "QUEUED", "PAUSE": "PAUSED", "RESUME": "QUEUED", "STOP": "STOPPING"}
    # START/RESUME → QUEUED so worker picks up; STOP → STOPPING then worker sets STOPPED
    if action == "START":
        run.status = "QUEUED"
        run.started_at = run.started_at or datetime.now(timezone.utc)
    elif action == "PAUSE":
        run.status = "PAUSED"
    elif action == "RESUME":
        run.status = "QUEUED"
    elif action == "STOP":
        run.status = "STOPPING"
    log = list(run.live_log or [])
    log.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": f"Control: {action}"})
    run.live_log = log[-200:]
    db.commit()
    return TestRunOut.model_validate(run)


# ── Results ───────────────────────────────────────────
@router.get("/results", response_model=List[TestResultOut])
def list_results(run_id: Optional[int] = None, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    q = db.query(TestResult).order_by(TestResult.id.desc())
    if run_id:
        q = q.filter(TestResult.run_id == run_id)
    return q.limit(500).all()


@router.get("/results/{rid}", response_model=TestResultOut)
def get_result(rid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    r = db.get(TestResult, rid)
    if not r:
        raise HTTPException(404)
    return r


# ── Runner settings ───────────────────────────────────
@router.get("/runner-settings", response_model=RunnerSettingsOut)
def get_runner(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    s = db.query(RunnerSettings).first()
    if not s:
        s = RunnerSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.put("/runner-settings", response_model=RunnerSettingsOut)
def put_runner(body: RunnerSettingsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    # Enforce decline_retry == 0 (forbidden to retry/rotate on decline)
    if body.decline_retry != 0:
        raise HTTPException(400, "decline_retry must be 0 (forbidden to auto-retry/rotate on CARD_DECLINED)")
    s = db.query(RunnerSettings).first()
    if not s:
        s = RunnerSettings()
        db.add(s)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    s.decline_retry = 0
    db.commit()
    db.refresh(s)
    return s


# ── Payrails ──────────────────────────────────────────
@router.get("/payrails-config", response_model=PayrailsConfigOut)
def get_payrails(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = db.query(PayrailsConfig).first()
    if not c:
        c = PayrailsConfig()
        db.add(c)
        db.commit()
        db.refresh(c)
    # Strip CVV from sandbox_cards in response display? Keep for admin fill but mask in logs
    cards = never_persist_cvv(dict(c.sandbox_cards or {})) if False else (c.sandbox_cards or {})
    # Actually sandbox_cards may contain cvv for fill — only return last4 style in list; admin panel needs them in memory
    # We store sandbox card CVV encrypted... For simplicity store in JSON but never log; admin responsibility for sandbox only
    return PayrailsConfigOut(
        id=c.id, sandbox_base_url=c.sandbox_base_url, merchant_id=c.merchant_id,
        has_api_key=bool(c.api_key_enc), public_key=c.public_key,
        iframe_selector=c.iframe_selector, card_number_selector=c.card_number_selector,
        expiry_selector=c.expiry_selector, cvv_selector=c.cvv_selector, submit_selector=c.submit_selector,
        result_selectors=c.result_selectors or {}, threeds_selectors=c.threeds_selectors or [],
        sandbox_cards=c.sandbox_cards or {}, notes=c.notes,
    )


@router.put("/payrails-config", response_model=PayrailsConfigOut)
def put_payrails(body: PayrailsConfigIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = db.query(PayrailsConfig).first()
    if not c:
        c = PayrailsConfig()
        db.add(c)
    c.sandbox_base_url = body.sandbox_base_url
    c.merchant_id = body.merchant_id
    if body.api_key:
        c.api_key_enc = encrypt_secret(body.api_key)
    c.public_key = body.public_key
    c.iframe_selector = body.iframe_selector
    c.card_number_selector = body.card_number_selector
    c.expiry_selector = body.expiry_selector
    c.cvv_selector = body.cvv_selector
    c.submit_selector = body.submit_selector
    c.result_selectors = body.result_selectors
    c.threeds_selectors = body.threeds_selectors
    # Sandbox cards: needed for fill; warn that CVV in sandbox_cards is sensitive — kept for sandbox QA only
    c.sandbox_cards = body.sandbox_cards or {}
    c.notes = body.notes
    db.commit()
    db.refresh(c)
    return get_payrails(db, admin)


# ── System settings / Logs / Help / Reports ───────────
@router.get("/system-settings")
def get_sys(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(SystemSettings).all()
    return {r.key: r.value for r in rows}


@router.put("/system-settings/{key}")
def put_sys(key: str, body: dict, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if not row:
        row = SystemSettings(key=key, value=body)
        db.add(row)
    else:
        row.value = body
    db.commit()
    return {"message": "ok"}


@router.get("/logs")
def list_logs(limit: int = 100, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(AppLog).order_by(AppLog.id.desc()).limit(limit).all()
    return [
        {"id": r.id, "level": r.level, "source": r.source, "message": r.message,
         "meta": redact_dict(r.meta), "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.get("/help/{page_key}")
def help_content(page_key: str):
    from app.services.help_content import get_help
    return get_help(page_key)


@router.get("/reports/export")
def export_report(
    run_id: Optional[int] = None,
    fmt: str = Query("json", pattern="^(csv|xlsx|json|html)$"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    q = db.query(TestResult).order_by(TestResult.id)
    if run_id:
        q = q.filter(TestResult.run_id == run_id)
    rows = q.all()

    def safe_row(r: TestResult) -> dict:
        return {
            "id": r.id, "run_id": r.run_id, "case_id": r.case_id, "case_name": r.case_name,
            "expected": r.expected, "actual": r.actual, "status": r.status,
            "duration_ms": r.duration_ms, "account_email": r.account_email,
            "network_profile": r.network_profile, "pan_masked": r.pan_masked,
            "error_message": r.error_message, "created_at": r.created_at.isoformat() if r.created_at else "",
        }

    data = [safe_row(r) for r in rows]
    if fmt == "json":
        return JSONResponse(data)
    if fmt == "csv":
        buf = io.StringIO()
        if data:
            w = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=report.csv"})
    if fmt == "html":
        html = "<html><body><h1>Payment QA Report</h1><table border=1><tr>"
        if data:
            html += "".join(f"<th>{k}</th>" for k in data[0]) + "</tr>"
            for row in data:
                html += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"
        html += "</table></body></html>"
        return HTMLResponse(html)
    if fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Results"
        if data:
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": "attachment; filename=report.xlsx"})
    raise HTTPException(400)


@router.get("/screenshots")
def list_screenshots(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    settings = get_settings()
    root = Path(settings.screenshot_dir)
    files = []
    if root.exists():
        for p in sorted(root.rglob("*.png"))[-200:]:
            files.append({"path": str(p), "name": p.name, "size": p.stat().st_size})
    return files


@router.get("/docs/screenshots/{name}")
def get_doc_screenshot(name: str):
    """Serve reference screenshots from docs."""
    from fastapi.responses import FileResponse
    base = Path(__file__).resolve().parents[2].parent / "docs" / "screenshots"
    path = (base / name).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


# ══════════════════════════════════════════════════════
# 1.2.0 — Batch / Preview / Export / Clone / Import Center
# ══════════════════════════════════════════════════════

class BatchIdsIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    enabled: Optional[bool] = None
    tag: Optional[str] = None
    status: Optional[str] = None


class ImportPreviewIn(BaseModel):
    text: str
    type: str  # accounts|proxies|cases|page_mapping|environment
    mapping: Optional[Dict[str, int]] = None
    delimiter: str = "auto"


def _preview_payload(parsed, typ: str) -> dict:
    # never echo passwords fully in preview — mask
    safe_items = []
    for it in parsed.items[:200]:
        row = dict(it)
        if "password" in row and row["password"]:
            row["password"] = "***"
        safe_items.append(row)
    return {
        "type": typ,
        "parsed": len(parsed.items),
        "errors": parsed.errors,
        "warnings": getattr(parsed, "warnings", []) or [],
        "items": safe_items,
        "valid": len(parsed.errors) == 0 or len(parsed.items) > 0,
    }


# ── Unified Import Center ─────────────────────────────
@router.get("/import/templates/{typ}")
def import_template(typ: str, admin: AdminUser = Depends(get_current_admin)):
    key = typ if typ in TEMPLATES else typ.replace("-", "_")
    if key == "page-mapping":
        key = "page_mapping"
    if key not in TEMPLATES:
        raise HTTPException(404, f"unknown template type: {typ}")
    content = TEMPLATES[key]
    media = "application/json" if key in ("page_mapping", "environment") else "text/plain"
    return PlainTextResponse(content, media_type=media)


@router.post("/import/preview")
def import_preview(body: ImportPreviewIn, admin: AdminUser = Depends(get_current_admin)):
    typ = body.type.replace("-", "_")
    if typ == "accounts":
        parsed = parse_qa_accounts(body.text)
    elif typ == "proxies":
        parsed = parse_socks5(body.text)
    elif typ in ("cases", "test_cases"):
        parsed = parse_test_cases(body.text, mapping=body.mapping, delimiter=body.delimiter)
        typ = "cases"
    elif typ == "page_mapping":
        parsed = parse_page_mappings_json(body.text)
    elif typ in ("environment", "environments"):
        parsed = parse_environment_json(body.text)
        typ = "environment"
    else:
        raise HTTPException(400, "type must be accounts|proxies|cases|page_mapping|environment")
    return _preview_payload(parsed, typ)


@router.post("/import/confirm")
def import_confirm(body: ImportPreviewIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    typ = body.type.replace("-", "_")
    created = updated = skipped = 0
    errors: List[str] = []

    if typ == "accounts":
        parsed = parse_qa_accounts(body.text)
        errors = list(parsed.errors)
        for item in parsed.items:
            if db.query(QAAccount).filter(QAAccount.email == item["email"]).first():
                skipped += 1
                continue
            db.add(QAAccount(
                email=item["email"],
                password_enc=encrypt_secret(item["password"]),
                display_name=item.get("display_name"),
                notes=item.get("notes") or item.get("tag"),
            ))
            created += 1
    elif typ == "proxies":
        parsed = parse_socks5(body.text)
        errors = list(parsed.errors)
        for item in parsed.items:
            exists = db.query(Socks5Proxy).filter(
                Socks5Proxy.host == item["host"], Socks5Proxy.port == item["port"],
                Socks5Proxy.username == item.get("username"),
            ).first()
            if exists:
                skipped += 1
                continue
            db.add(Socks5Proxy(
                host=item["host"], port=item["port"], username=item.get("username"),
                password_enc=encrypt_secret(item["password"]) if item.get("password") else None,
            ))
            created += 1
    elif typ in ("cases", "test_cases"):
        parsed = parse_test_cases(body.text, mapping=body.mapping, delimiter=body.delimiter)
        errors = list(parsed.errors)
        for item in parsed.items:
            item = never_persist_cvv(item)
            existing = db.query(TestCase).filter(TestCase.case_id == item["case_id"]).first()
            if existing:
                for k, v in item.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(TestCase(**item))
                created += 1
    elif typ == "page_mapping":
        parsed = parse_page_mappings_json(body.text)
        errors = list(parsed.errors)
        for item in parsed.items:
            existing = db.query(PageMapping).filter(PageMapping.key == item["key"]).first()
            if existing:
                for k, v in item.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(PageMapping(**item))
                created += 1
    elif typ in ("environment", "environments"):
        parsed = parse_environment_json(body.text)
        errors = list(parsed.errors)
        for item in parsed.items:
            warnings = validate_environment_url(item["base_url"], item["env_type"])
            domains = list(item.get("allowed_domains") or [])
            if not domains:
                from app.services.allowlist import extract_host
                h = extract_host(item["base_url"])
                if h:
                    domains = [h]
            db.add(Environment(**{**item, "allowed_domains": domains}))
            created += 1
    else:
        raise HTTPException(400, "type must be accounts|proxies|cases|page_mapping|environment")

    db.commit()
    return {
        "type": typ, "created": created, "updated": updated, "skipped": skipped,
        "errors": errors, "parsed": created + updated + skipped,
    }


# ── SOCKS5 batch / edit / export / test-all ───────────
@router.put("/proxies/{pid}", response_model=Socks5Out)
def update_proxy(pid: int, body: Socks5In, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    p = db.get(Socks5Proxy, pid)
    if not p:
        raise HTTPException(404)
    p.host = body.host
    p.port = body.port
    p.username = body.username
    p.label = body.label
    p.is_active = body.is_active
    if body.password:
        p.password_enc = encrypt_secret(body.password)
    db.commit()
    db.refresh(p)
    return p


@router.post("/proxies/preview")
def proxies_preview(body: ImportMappingIn, admin: AdminUser = Depends(get_current_admin)):
    return _preview_payload(parse_socks5(body.text), "proxies")


@router.post("/proxies/import/confirm")
def proxies_import_confirm(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return import_confirm(ImportPreviewIn(text=body.text, type="proxies"), db, admin)


@router.post("/proxies/batch")
def proxies_batch(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    action_enabled = body.enabled
    deleted = 0
    updated = 0
    for pid in body.ids:
        p = db.get(Socks5Proxy, pid)
        if not p:
            continue
        if action_enabled is None and body.status == "delete":
            db.delete(p)
            deleted += 1
        elif body.status == "delete":
            db.delete(p)
            deleted += 1
        elif action_enabled is not None:
            p.is_active = bool(action_enabled)
            updated += 1
    db.commit()
    return {"updated": updated, "deleted": deleted}


@router.post("/proxies/batch-delete")
def proxies_batch_delete(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    for pid in body.ids:
        p = db.get(Socks5Proxy, pid)
        if p:
            db.delete(p)
            n += 1
    db.commit()
    return {"deleted": n}


@router.post("/proxies/batch-enable")
def proxies_batch_enable(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    for pid in body.ids:
        p = db.get(Socks5Proxy, pid)
        if p:
            p.is_active = True if body.enabled is None else bool(body.enabled)
            n += 1
    db.commit()
    return {"updated": n}


@router.post("/proxies/test-all")
def proxies_test_all(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    settings = get_settings()
    sys_row = db.query(SystemSettings).filter(SystemSettings.key == "proxy_test_url").first()
    test_url = None
    if sys_row and isinstance(sys_row.value, dict):
        test_url = sys_row.value.get("url") or sys_row.value.get("proxy_test_url")
    test_url = test_url or settings.proxy_test_url
    results = []
    for p in db.query(Socks5Proxy).filter(Socks5Proxy.is_active == True).all():  # noqa: E712
        pwd = decrypt_secret(p.password_enc) if p.password_enc else None
        result = probe_socks5(p.host, p.port, username=p.username, password=pwd, test_url=test_url, timeout=8.0, fetch_exit_ip=True)
        status_str = result.status if result.status != "UNKNOWN" else "HANDSHAKE_ERROR"
        p.status = status_str
        p.latency_ms = result.latency_ms
        p.exit_ip = result.exit_ip
        p.last_tested_at = datetime.now(timezone.utc)
        results.append({"id": p.id, "status": status_str, "latency_ms": result.latency_ms, "exit_ip": result.exit_ip})
    db.commit()
    return {"tested": len(results), "results": results}


@router.get("/proxies/export")
def proxies_export(fmt: str = Query("txt", pattern="^(txt|csv)$"), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(Socks5Proxy).order_by(Socks5Proxy.id).all()
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["host", "port", "username", "status", "latency_ms", "exit_ip", "last_tested_at", "is_active", "label"])
        for p in rows:
            w.writerow([p.host, p.port, p.username or "", p.status, p.latency_ms or "", p.exit_ip or "",
                        p.last_tested_at.isoformat() if p.last_tested_at else "", p.is_active, p.label or ""])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=proxies.csv"})
    lines = []
    for p in rows:
        if p.username:
            # password not exported for safety — host:port:user
            lines.append(f"{p.host}:{p.port}:{p.username}:")
        else:
            lines.append(f"{p.host}:{p.port}")
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""),
                             headers={"Content-Disposition": "attachment; filename=proxies.txt"})


# ── QA Accounts batch / export / preview ──────────────
@router.put("/accounts/{aid}", response_model=QAAccountOut)
def update_account(aid: int, body: dict, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    a = db.get(QAAccount, aid)
    if not a:
        raise HTTPException(404)
    if "display_name" in body:
        a.display_name = body.get("display_name")
    if "notes" in body:
        a.notes = body.get("notes")
    if "status" in body and body["status"] in ("READY", "COOLDOWN", "DISABLED", "BUSY"):
        a.status = body["status"]
    if body.get("password"):
        a.password_enc = encrypt_secret(body["password"])
    db.commit()
    db.refresh(a)
    return a


@router.post("/accounts/preview")
def accounts_preview(body: ImportMappingIn, admin: AdminUser = Depends(get_current_admin)):
    return _preview_payload(parse_qa_accounts(body.text), "accounts")


@router.post("/accounts/batch-delete")
def accounts_batch_delete(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    for aid in body.ids:
        a = db.get(QAAccount, aid)
        if a:
            db.delete(a)
            n += 1
    db.commit()
    return {"deleted": n}


@router.post("/accounts/batch-status")
def accounts_batch_status(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    status = body.status or ("DISABLED" if body.enabled is False else "READY")
    n = 0
    for aid in body.ids:
        a = db.get(QAAccount, aid)
        if a:
            a.status = status
            n += 1
    db.commit()
    return {"updated": n}


@router.post("/accounts/batch-tag")
def accounts_batch_tag(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    for aid in body.ids:
        a = db.get(QAAccount, aid)
        if a:
            a.notes = body.tag or a.notes
            n += 1
    db.commit()
    return {"updated": n}


@router.get("/accounts/export")
def accounts_export(fmt: str = Query("txt", pattern="^(txt|csv)$"), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(QAAccount).order_by(QAAccount.id).all()
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "email", "display_name", "status", "notes", "consecutive_failures"])
        for a in rows:
            w.writerow([a.id, a.email, a.display_name or "", a.status, a.notes or "", a.consecutive_failures])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=accounts.csv"})
    # passwords never exported
    lines = [f"{a.display_name or ''}|{a.email}|***|{a.notes or ''}".strip("|") for a in rows]
    # simpler: email only listing
    lines = [f"{a.email}|********|{a.notes or ''}" for a in rows]
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""),
                             headers={"Content-Disposition": "attachment; filename=accounts.txt"})


# ── Test Cases batch / export / preview ───────────────
@router.post("/test-cases/preview")
def cases_preview(body: ImportMappingIn, admin: AdminUser = Depends(get_current_admin)):
    return _preview_payload(parse_test_cases(body.text, mapping=body.mapping, delimiter=body.delimiter), "cases")


@router.post("/test-cases/batch-delete")
def cases_batch_delete(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    for cid in body.ids:
        c = db.get(TestCase, cid)
        if c:
            db.delete(c)
            n += 1
    db.commit()
    return {"deleted": n}


@router.post("/test-cases/batch-enable")
def cases_batch_enable(body: BatchIdsIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    n = 0
    enabled = True if body.enabled is None else bool(body.enabled)
    for cid in body.ids:
        c = db.get(TestCase, cid)
        if c:
            c.is_active = enabled
            n += 1
    db.commit()
    return {"updated": n}


@router.get("/test-cases/export")
def cases_export(fmt: str = Query("txt", pattern="^(txt|csv)$"), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(TestCase).order_by(TestCase.id).all()
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["case_id", "name", "payment_test_ref", "expected_result", "card_brand", "pan_masked", "expiry", "tags", "notes", "is_active"])
        for c in rows:
            notes = (c.extra or {}).get("notes", "") if isinstance(c.extra, dict) else ""
            w.writerow([c.case_id, c.name, c.payment_test_ref, c.expected_result, c.card_brand or "",
                        c.pan_masked or "", c.expiry or "", ",".join(c.tags or []), notes, c.is_active])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=test_cases.csv"})
    lines = []
    for c in rows:
        notes = (c.extra or {}).get("notes", "") if isinstance(c.extra, dict) else ""
        last4 = ""
        if c.pan_masked and c.pan_masked[-4:].isdigit():
            last4 = c.pan_masked[-4:]
        tag = ",".join(c.tags or [])
        lines.append("|".join([
            c.case_id, c.name, c.payment_test_ref or "", c.expected_result,
            c.card_brand or "", last4, c.expiry or "", tag, notes,
        ]))
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""),
                             headers={"Content-Disposition": "attachment; filename=test_cases.txt"})


# ── Environments clone / import / export ──────────────
@router.post("/environments/{env_id}/clone", response_model=EnvironmentOut)
def clone_env(env_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    env = db.get(Environment, env_id)
    if not env:
        raise HTTPException(404)
    clone = Environment(
        name=f"{env.name} (copy)",
        base_url=env.base_url,
        allowed_domains=list(env.allowed_domains or []),
        env_type=env.env_type,
        is_active=False,
        notes=env.notes,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/environments/export")
def env_export(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(Environment).order_by(Environment.id).all()
    data = [
        {
            "name": e.name, "base_url": e.base_url, "allowed_domains": e.allowed_domains or [],
            "env_type": e.env_type, "is_active": e.is_active, "notes": e.notes,
        }
        for e in rows
    ]
    return JSONResponse(data, headers={"Content-Disposition": "attachment; filename=environments.json"})


@router.post("/environments/import")
def env_import(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return import_confirm(ImportPreviewIn(text=body.text, type="environment"), db, admin)


# ── Page Mapping delete / import / export / copy ──────
@router.delete("/page-mappings/{mid}")
def delete_mapping(mid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = db.get(PageMapping, mid)
    if not m:
        raise HTTPException(404)
    db.delete(m)
    db.commit()
    return {"message": "deleted"}


@router.post("/page-mappings/{mid}/copy", response_model=PageMappingOut)
def copy_mapping(mid: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = db.get(PageMapping, mid)
    if not m:
        raise HTTPException(404)
    new_key = f"{m.key}.copy"
    n = 1
    while db.query(PageMapping).filter(PageMapping.key == new_key).first():
        n += 1
        new_key = f"{m.key}.copy{n}"
    clone = PageMapping(
        key=new_key, label=f"{m.label} (copy)", page_group=m.page_group,
        selector_type=m.selector_type, selector=m.selector, iframe_selector=m.iframe_selector,
        is_example=m.is_example, help_zh=m.help_zh, help_en=m.help_en, sort_order=m.sort_order,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/page-mappings/export")
def mappings_export(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.query(PageMapping).order_by(PageMapping.sort_order).all()
    data = [
        {
            "key": m.key, "label": m.label, "page_group": m.page_group,
            "selector_type": m.selector_type, "selector": m.selector,
            "iframe_selector": m.iframe_selector, "is_example": m.is_example,
            "help_zh": m.help_zh, "help_en": m.help_en, "sort_order": m.sort_order,
        }
        for m in rows
    ]
    return JSONResponse(data, headers={"Content-Disposition": "attachment; filename=page_mappings.json"})


@router.post("/page-mappings/import")
def mappings_import(body: ImportMappingIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return import_confirm(ImportPreviewIn(text=body.text, type="page_mapping"), db, admin)


# ── Screenshots download ──────────────────────────────
@router.get("/screenshots/download")
def download_screenshot(path: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    settings = get_settings()
    root = Path(settings.screenshot_dir).resolve()
    target = Path(path).resolve()
    if not str(target).startswith(str(root)) or not target.exists():
        # also allow relative name under screenshot dir
        target = (root / Path(path).name).resolve()
        if not str(target).startswith(str(root)) or not target.exists():
            raise HTTPException(404)
    from fastapi.responses import FileResponse
    return FileResponse(target, filename=target.name)


@router.get("/version")
def api_version():
    return {"version": "1.2.0", "name": "Payment QA Runner"}
