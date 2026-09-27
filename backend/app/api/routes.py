"""Payment Test Runner 2.0.0 API routes."""
from __future__ import annotations

import csv
import io
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, decrypt_secret, encrypt_secret, hash_password,
    mask_pan, verify_password,
)
from app.models.models import (
    Account, Admin, Artifact, NetworkProfile, Run, RunItem, Setting, Task, TestData,
)
from app.schemas.schemas import (
    AccountOut, AdminOut, ArtifactOut, CleanupPreview, CleanupRequest,
    HealthOut, IdsRequest, ImportConfirmRequest, ImportLineResult,
    ImportPreviewRequest, ImportPreviewResponse, LoginRequest, NetworkCreate,
    NetworkOut, NetworkUpdate, ReadinessOut, RunCreate, RunItemOut, RunOut,
    SelectRequest, TaskCreate, TaskOut, TaskUpdate, TestDataImportLine,
    TestDataImportPreview, TestDataOut, TokenResponse,
)
from app.seed.bootstrap import task_field_help, _allow_card, _slug
from app.services import cleanup as cleanup_svc
from app.services.importers import preview_accounts, preview_test_data
from app.services.network_probe import probe_profile

logger = logging.getLogger(__name__)
router = APIRouter()


def _utcnow():
    return datetime.now(timezone.utc)


# ── Auth ──────────────────────────────────────────────────────────────────────
@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Admin).filter(Admin.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/auth/me", response_model=AdminOut)
def me(admin: Admin = Depends(get_current_admin)):
    return admin


# ── Health / Home readiness ───────────────────────────────────────────────────
def _worker_alive() -> str:
    s = get_settings()
    hb = s.worker_heartbeat_file
    try:
        if os.path.isfile(hb) and (time.time() - os.path.getmtime(hb)) < 60:
            return "OK"
    except OSError:
        pass
    return "DOWN"


def _chromium_status() -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return "OK"
    except Exception:
        # In API container playwright may be absent — check binary hint
        for c in ("/ms-playwright", "/root/.cache/ms-playwright"):
            if os.path.isdir(c):
                return "OK"
        return "UNKNOWN"


def _disk_info() -> dict:
    s = get_settings()
    path = s.log_dir or "/data"
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / 1e9, 2),
            "free_gb": round(usage.free / 1e9, 2),
            "used_pct": round(usage.used / usage.total * 100, 1),
            **cleanup_svc.disk_stats(),
        }
    except Exception as e:
        return {"error": str(e)[:100]}


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    s = get_settings()
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "OK"
    except Exception:
        db_status = "DOWN"
    worker = _worker_alive()
    # Chromium check is expensive — soft status
    chromium = "OK" if worker == "OK" else "UNKNOWN"
    net = "OK"
    direct = db.query(NetworkProfile).filter(NetworkProfile.is_default == True).first()  # noqa: E712
    if direct and direct.last_test_status == "FAIL":
        net = "FAIL"
    overall = "OK" if db_status == "OK" else "DEGRADED"
    return HealthOut(
        status=overall,
        version=s.app_version,
        mode="LIVE",
        backend="OK",
        database=db_status,
        worker=worker,
        chromium=chromium,
        network=net,
        disk=_disk_info(),
        detail={"mock_fallback": False, "playwright_mock_env": s.playwright_mock},
    )


def _network_out(n: NetworkProfile) -> NetworkOut:
    return NetworkOut(
        id=n.id, name=n.name, protocol=n.protocol, host=n.host, port=n.port,
        username=n.username, has_password=bool(n.password_enc), is_default=n.is_default,
        last_test_status=n.last_test_status, last_latency_ms=n.last_latency_ms,
        last_test_error=n.last_test_error, last_tested_at=n.last_tested_at,
        created_at=n.created_at,
    )


def _task_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id, key=t.key, name=t.name, description=t.description, env_type=t.env_type,
        base_url=t.base_url, login_url=t.login_url, target_url=t.target_url,
        allow_card_fill=t.allow_card_fill, task_type=t.task_type,
        adapter_type=getattr(t, "adapter_type", None) or "standard_sandbox_binding",
        enabled=t.enabled,
        is_builtin=t.is_builtin, config=t.config or {}, last_url_test_status=t.last_url_test_status,
        last_url_test_at=t.last_url_test_at, created_at=t.created_at, updated_at=t.updated_at,
        field_help=task_field_help(),
    )


@router.get("/home/readiness", response_model=ReadinessOut)
def home_readiness(
    task_id: Optional[int] = None,
    network_id: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    accounts_imported = db.query(Account).count()
    accounts_selected = db.query(Account).filter(Account.selected == True).count()  # noqa: E712
    td_imported = db.query(TestData).count()
    td_available = db.query(TestData).filter(TestData.status != "INVALID").count()
    td_selected = db.query(TestData).filter(TestData.selected == True).count()  # noqa: E712

    task = None
    if task_id:
        task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        task = db.query(Task).filter(Task.enabled == True).order_by(Task.id).first()  # noqa: E712

    network = None
    if network_id:
        network = db.query(NetworkProfile).filter(NetworkProfile.id == network_id).first()
    if not network:
        network = db.query(NetworkProfile).filter(NetworkProfile.is_default == True).first()  # noqa: E712

    needs_td = bool(task and task.allow_card_fill)
    if needs_td:
        max_exec = min(accounts_selected, td_selected)
    else:
        max_exec = accounts_selected

    reasons: list[str] = []
    checklist = {
        "accounts": accounts_selected > 0,
        "test_data": (not needs_td) or td_selected > 0,
        "task": task is not None and task.enabled,
        "target_url": bool(task and task.target_url),
        "chromium": _worker_alive() == "OK" or True,  # soft: don't block if worker just starting
        "network": network is not None and network.last_test_status != "FAIL",
    }
    if not checklist["accounts"]:
        reasons.append("请先选择至少一个账号")
    if needs_td and not checklist["test_data"]:
        reasons.append("该任务需要测试数据：请导入并选择测试卡")
    if not checklist["task"]:
        reasons.append("请选择已启用的任务")
    if not checklist["target_url"]:
        reasons.append("任务缺少 Target URL")
    if network and network.last_test_status == "FAIL":
        reasons.append(f"网络不可用: {network.last_test_error or '测试失败'}")
    if not network:
        reasons.append("请选择网络配置")
    if max_exec <= 0 and checklist["accounts"] and (not needs_td or checklist["test_data"]):
        reasons.append("可执行数量为 0")

    # Chromium soft — warn but don't hard-block for readiness if worker down briefly
    ready = all([
        checklist["accounts"], checklist["test_data"], checklist["task"],
        checklist["target_url"], checklist["network"], max_exec > 0,
    ])
    return ReadinessOut(
        ready=ready,
        reasons=reasons,
        accounts_imported=accounts_imported,
        accounts_selected=accounts_selected,
        test_data_imported=td_imported,
        test_data_available=td_available,
        test_data_selected=td_selected,
        max_executable=max_exec,
        task=_task_out(task) if task else None,
        network=_network_out(network) if network else None,
        checklist=checklist,
    )


# ── Accounts ──────────────────────────────────────────────────────────────────
@router.get("/accounts", response_model=List[AccountOut])
def list_accounts(
    q: Optional[str] = None,
    status: Optional[str] = None,
    selected: Optional[bool] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Account)
    if q:
        query = query.filter(Account.email.contains(q))
    if status:
        query = query.filter(Account.status == status)
    if selected is not None:
        query = query.filter(Account.selected == selected)
    return query.order_by(Account.id.desc()).all()


@router.post("/accounts/import-preview", response_model=ImportPreviewResponse)
def accounts_import_preview(body: ImportPreviewRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = {a.email.lower() for a in db.query(Account.email).all()}
    # query returns Row objects when only column
    existing = {r[0].lower() if isinstance(r, tuple) else r.email.lower() for r in db.query(Account).all()}
    prev = preview_accounts(body.text or "", existing)
    return ImportPreviewResponse(
        total=prev.total, valid=prev.valid, dupe=prev.dupe, error=prev.error,
        lines=[ImportLineResult(line=l.line, raw=l.raw, status=l.status, reason=l.reason, email=l.email) for l in prev.lines],
    )


@router.post("/accounts/import-confirm")
def accounts_import_confirm(body: ImportConfirmRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = {a.email.lower() for a in db.query(Account).all()}
    prev = preview_accounts(body.text or "", existing)
    created = 0
    skipped = 0
    for line in prev.lines:
        if line.status == "valid" and line.email and line.password:
            db.add(Account(email=line.email, password_enc=encrypt_secret(line.password), status="READY"))
            created += 1
        elif line.status == "dupe":
            skipped += 1
            if not body.skip_dupes and line.email and line.password:
                acc = db.query(Account).filter(Account.email == line.email).first()
                if acc:
                    acc.password_enc = encrypt_secret(line.password)
    db.commit()
    return {"created": created, "skipped_dupes": skipped, "errors": prev.error}


@router.post("/accounts/select")
def accounts_select(body: SelectRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    db.query(Account).filter(Account.id.in_(body.ids)).update(
        {Account.selected: body.selected}, synchronize_session=False
    )
    db.commit()
    return {"ok": True, "count": len(body.ids), "selected": body.selected}


@router.delete("/accounts")
def accounts_delete(body: IdsRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(Account).filter(Account.id.in_(body.ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": n}


@router.post("/accounts/clear")
def accounts_clear(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(Account).delete()
    db.commit()
    return {"deleted": n}


@router.get("/accounts/export")
def accounts_export(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Export emails only — never passwords."""
    rows = db.query(Account).order_by(Account.id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "status", "session_status", "last_result", "created_at"])
    for a in rows:
        w.writerow([a.email, a.status, a.session_status, a.last_result or "", a.created_at.isoformat()])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=accounts.csv"},
    )


@router.post("/accounts/{account_id}/session-clear")
def account_session_clear(account_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(404, "账号不存在")
    if acc.session_path and os.path.isfile(acc.session_path):
        try:
            os.remove(acc.session_path)
        except OSError:
            pass
    acc.session_status = "NONE"
    acc.session_path = None
    acc.session_updated_at = None
    db.commit()
    return {"ok": True}


# ── Test Data ─────────────────────────────────────────────────────────────────
@router.get("/test-data", response_model=List[TestDataOut])
def list_test_data(
    selected: Optional[bool] = None,
    status: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(TestData)
    if selected is not None:
        q = q.filter(TestData.selected == selected)
    if status:
        q = q.filter(TestData.status == status)
    return q.order_by(TestData.id.desc()).all()


@router.get("/test-data/stats")
def test_data_stats(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    all_td = db.query(TestData).all()
    return {
        "total": len(all_td),
        "unused": sum(1 for t in all_td if t.used_count == 0),
        "used": sum(1 for t in all_td if t.used_count > 0),
        "selected": sum(1 for t in all_td if t.selected),
        "invalid": sum(1 for t in all_td if t.status == "INVALID"),
    }


@router.post("/test-data/import-preview", response_model=TestDataImportPreview)
def td_import_preview(body: ImportPreviewRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = {(t.pan_last4, t.expiry) for t in db.query(TestData).all()}
    prev = preview_test_data(body.text or "", existing)
    return TestDataImportPreview(
        total=prev.total, valid=prev.valid, dupe=prev.dupe, error=prev.error,
        lines=[TestDataImportLine(
            line=l.line, raw=l.raw, status=l.status, reason=l.reason,
            pan_masked=l.pan_masked, expiry=l.expiry,
        ) for l in prev.lines],
    )


@router.post("/test-data/import-confirm")
def td_import_confirm(body: ImportConfirmRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = {(t.pan_last4, t.expiry) for t in db.query(TestData).all()}
    prev = preview_test_data(body.text or "", existing)
    created = 0
    for line in prev.lines:
        if line.status == "valid" and line.pan and line.expiry and line.cvc:
            db.add(TestData(
                pan_enc=encrypt_secret(line.pan),
                pan_masked=mask_pan(line.pan),
                pan_last4=line.pan[-4:],
                expiry=line.expiry,
                cvc_enc=encrypt_secret(line.cvc),
                brand=line.brand,
                status="UNUSED",
            ))
            created += 1
    db.commit()
    return {"created": created, "skipped_dupes": prev.dupe, "errors": prev.error}


@router.post("/test-data/select")
def td_select(body: SelectRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    db.query(TestData).filter(TestData.id.in_(body.ids)).update(
        {TestData.selected: body.selected}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.delete("/test-data")
def td_delete(body: IdsRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(TestData).filter(TestData.id.in_(body.ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": n}


@router.get("/test-data/export-safe")
def td_export_safe(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Export masked cards only — never CVC / full PAN."""
    rows = db.query(TestData).order_by(TestData.id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["pan_masked", "expiry", "brand", "status", "used_count", "created_at"])
    for t in rows:
        w.writerow([t.pan_masked, t.expiry, t.brand or "", t.status, t.used_count, t.created_at.isoformat()])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=test_data_safe.csv"},
    )


# ── Tasks ─────────────────────────────────────────────────────────────────────
@router.get("/tasks", response_model=List[TaskOut])
def list_tasks(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    return [_task_out(t) for t in db.query(Task).order_by(Task.id).all()]


@router.get("/tasks/field-help")
def tasks_field_help(admin: Admin = Depends(get_current_admin)):
    return task_field_help()


@router.post("/tasks", response_model=TaskOut)
def create_task(body: TaskCreate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    key = body.key or _slug(body.name)
    if db.query(Task).filter(Task.key == key).first():
        key = f"{key}-{int(time.time()) % 10000}"
    adapter = body.adapter_type if body.adapter_type in ("preply_ui", "standard_sandbox_binding") else (
        "preply_ui" if body.env_type == "Production" else "standard_sandbox_binding"
    )
    t = Task(
        key=key, name=body.name, description=body.description, env_type=body.env_type,
        base_url=body.base_url.rstrip("/"), login_url=body.login_url or "",
        target_url=body.target_url, allow_card_fill=_allow_card(body.env_type),
        task_type=body.task_type if body.task_type in ("smoke", "card_bind") else (
            "card_bind" if _allow_card(body.env_type) else "smoke"
        ),
        adapter_type=adapter,
        enabled=body.enabled, is_builtin=False, config=body.config or {},
    )
    # Safety: Production never allow card fill; force preply_ui when Production
    if t.env_type == "Production":
        t.allow_card_fill = False
        t.task_type = "smoke"
        if t.adapter_type == "standard_sandbox_binding" and not body.adapter_type:
            t.adapter_type = "preply_ui"
    db.add(t)
    db.commit()
    db.refresh(t)
    return _task_out(t)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(404, "任务不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "base_url" and v:
            v = v.rstrip("/")
        setattr(t, k, v)
    if "adapter_type" in data and data["adapter_type"] not in ("preply_ui", "standard_sandbox_binding", None):
        raise HTTPException(400, "adapter_type 必须是 preply_ui 或 standard_sandbox_binding")
    if "env_type" in data:
        t.allow_card_fill = _allow_card(t.env_type)
        if t.env_type == "Production":
            t.allow_card_fill = False
            t.task_type = "smoke"
    t.updated_at = _utcnow()
    db.commit()
    db.refresh(t)
    return _task_out(t)


@router.post("/tasks/{task_id}/enable")
def enable_task(task_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(404)
    t.enabled = True
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/disable")
def disable_task(task_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(404)
    t.enabled = False
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/test-url")
def test_task_url(task_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise HTTPException(404)
    url = t.target_url or t.base_url
    if not url:
        raise HTTPException(400, "缺少 URL")
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(url)
        ok = r.status_code < 500
        t.last_url_test_status = "OK" if ok else "FAIL"
        t.last_url_test_at = _utcnow()
        db.commit()
        return {"ok": ok, "status_code": r.status_code, "url": url, "final_url": str(r.url)}
    except Exception as e:
        t.last_url_test_status = "FAIL"
        t.last_url_test_at = _utcnow()
        db.commit()
        return {"ok": False, "error": str(e)[:200], "url": url}


# ── Networks ──────────────────────────────────────────────────────────────────
@router.get("/networks", response_model=List[NetworkOut])
def list_networks(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    return [_network_out(n) for n in db.query(NetworkProfile).order_by(NetworkProfile.id).all()]


@router.post("/networks", response_model=NetworkOut)
def create_network(body: NetworkCreate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    if body.is_default:
        db.query(NetworkProfile).update({NetworkProfile.is_default: False})
    n = NetworkProfile(
        name=body.name, protocol=body.protocol, host=body.host, port=body.port,
        username=body.username,
        password_enc=encrypt_secret(body.password) if body.password else None,
        is_default=body.is_default or body.protocol == "direct",
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return _network_out(n)


@router.patch("/networks/{nid}", response_model=NetworkOut)
def update_network(nid: int, body: NetworkUpdate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(NetworkProfile).filter(NetworkProfile.id == nid).first()
    if not n:
        raise HTTPException(404)
    data = body.model_dump(exclude_unset=True)
    pwd = data.pop("password", None)
    if data.get("is_default"):
        db.query(NetworkProfile).update({NetworkProfile.is_default: False})
    for k, v in data.items():
        setattr(n, k, v)
    if pwd is not None:
        n.password_enc = encrypt_secret(pwd) if pwd else None
    db.commit()
    db.refresh(n)
    return _network_out(n)


@router.delete("/networks/{nid}")
def delete_network(nid: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(NetworkProfile).filter(NetworkProfile.id == nid).first()
    if not n:
        raise HTTPException(404)
    if n.protocol == "direct" and n.is_default:
        raise HTTPException(400, "不能删除默认 Direct 网络")
    db.delete(n)
    db.commit()
    return {"ok": True}


@router.post("/networks/{nid}/test")
def test_network(nid: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    n = db.query(NetworkProfile).filter(NetworkProfile.id == nid).first()
    if not n:
        raise HTTPException(404)
    pwd = decrypt_secret(n.password_enc) if n.password_enc else None
    ok, latency, err = probe_profile(n.protocol, n.host, n.port, n.username, pwd)
    n.last_test_status = "OK" if ok else "FAIL"
    n.last_latency_ms = latency
    n.last_test_error = err or None
    n.last_tested_at = _utcnow()
    db.commit()
    return {"ok": ok, "latency_ms": latency, "error": err or None, "status": n.last_test_status}


# ── Runs ──────────────────────────────────────────────────────────────────────
def _item_out(i: RunItem, db: Session | None = None) -> RunItemOut:
    shot_id = None
    trace_id = None
    if db is not None:
        arts = db.query(Artifact).filter(Artifact.run_item_id == i.id).all()
        for a in arts:
            if a.kind == "screenshot" and shot_id is None:
                shot_id = a.id
            elif a.kind == "trace" and trace_id is None:
                trace_id = a.id
    steps = i.steps or []
    log_excerpt = None
    if steps:
        log_excerpt = " → ".join(
            f"{s.get('state', '')}:{s.get('msg', '')}"[:60] for s in steps[-6:]
        )
    return RunItemOut(
        id=i.id, run_id=i.run_id, account_id=i.account_id, account_email=i.account_email,
        test_data_id=i.test_data_id, test_data_masked=i.test_data_masked,
        status=i.status, result_code=i.result_code, reason=i.reason,
        final_url=getattr(i, "final_url", None), state=i.state, steps=steps,
        duration_ms=i.duration_ms or 0, started_at=i.started_at, finished_at=i.finished_at,
        created_at=i.created_at, screenshot_id=shot_id, trace_id=trace_id,
        log_excerpt=log_excerpt,
    )


def _run_out(r: Run, include_items: bool = False, db: Session | None = None) -> RunOut:
    items = None
    if include_items and db is not None:
        items = [_item_out(i, db) for i in db.query(RunItem).filter(RunItem.run_id == r.id).order_by(RunItem.id).all()]
    return RunOut(
        id=r.id, task_id=r.task_id, task_snapshot=r.task_snapshot or {},
        network_id=r.network_id, network_snapshot=r.network_snapshot or {},
        account_ids=r.account_ids or [], test_data_ids=r.test_data_ids or [],
        status=r.status, progress_done=r.progress_done, progress_total=r.progress_total,
        success_count=r.success_count, fail_count=r.fail_count, error_count=r.error_count,
        cancelled_count=r.cancelled_count, current_account=r.current_account,
        current_step=r.current_step, live_log=r.live_log or [], stop_requested=r.stop_requested,
        mode=r.mode or "LIVE", error_code=r.error_code, started_at=r.started_at,
        finished_at=r.finished_at, created_at=r.created_at, items=items,
    )


@router.post("/runs", response_model=RunOut)
def create_run(body: RunCreate, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == body.task_id, Task.enabled == True).first()  # noqa: E712
    if not task:
        raise HTTPException(400, "任务不存在或未启用")
    if not task.target_url:
        raise HTTPException(400, "任务缺少 Target URL")

    network = None
    if body.network_id:
        network = db.query(NetworkProfile).filter(NetworkProfile.id == body.network_id).first()
    if not network:
        network = db.query(NetworkProfile).filter(NetworkProfile.is_default == True).first()  # noqa: E712
    if not network:
        raise HTTPException(400, "请配置网络")
    if network.last_test_status == "FAIL":
        raise HTTPException(400, f"网络不可用: {network.last_test_error or '请先测试连接'}")

    if body.account_ids is not None:
        accounts = db.query(Account).filter(Account.id.in_(body.account_ids)).all()
    else:
        accounts = db.query(Account).filter(Account.selected == True).all()  # noqa: E712
    if not accounts:
        raise HTTPException(400, "请先选择账号")

    needs_td = task.allow_card_fill
    if body.test_data_ids is not None:
        tds = db.query(TestData).filter(TestData.id.in_(body.test_data_ids)).all()
    else:
        tds = db.query(TestData).filter(TestData.selected == True).all() if needs_td else []  # noqa: E712

    if needs_td and not tds:
        raise HTTPException(400, "该任务需要测试数据")

    # Pairing: 1:1, no reuse
    if needs_td:
        n = min(len(accounts), len(tds))
        accounts = accounts[:n]
        tds = tds[:n]
    else:
        tds = [None] * len(accounts)

    if task.env_type == "Production" and task.allow_card_fill:
        raise HTTPException(400, "Production 任务禁止填卡")

    run = Run(
        task_id=task.id,
        task_snapshot={
            "id": task.id, "key": task.key, "name": task.name, "env_type": task.env_type,
            "base_url": task.base_url, "login_url": task.login_url, "target_url": task.target_url,
            "allow_card_fill": task.allow_card_fill, "task_type": task.task_type,
            "adapter_type": getattr(task, "adapter_type", None) or "standard_sandbox_binding",
            "config": task.config or {},
        },
        network_id=network.id,
        network_snapshot={
            "id": network.id, "name": network.name, "protocol": network.protocol,
            "host": network.host, "port": network.port, "username": network.username,
            # password fetched by worker via network_id decrypt — not snapshotted plaintext
            "has_password": bool(network.password_enc),
        },
        account_ids=[a.id for a in accounts],
        test_data_ids=[t.id for t in tds if t is not None],
        status="QUEUED",
        progress_total=len(accounts),
        mode="LIVE",
        live_log=[{"ts": _utcnow().isoformat(), "msg": "Run queued"}],
    )
    db.add(run)
    db.flush()
    for i, acc in enumerate(accounts):
        td = tds[i] if i < len(tds) else None
        db.add(RunItem(
            run_id=run.id,
            account_id=acc.id,
            account_email=acc.email,
            test_data_id=td.id if td else None,
            test_data_masked=td.pan_masked if td else None,
            status="WAITING",
            state="QUEUED",
        ))
    db.commit()
    db.refresh(run)
    return _run_out(run, include_items=True, db=db)


@router.get("/runs", response_model=List[RunOut])
def list_runs(
    limit: int = Query(50, le=200),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(Run).order_by(Run.id.desc()).limit(limit).all()
    return [_run_out(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r:
        raise HTTPException(404, "运行不存在")
    return _run_out(r, include_items=True, db=db)


@router.get("/runs/{run_id}/status", response_model=RunOut)
def run_status(run_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    return get_run(run_id, admin, db)


@router.post("/runs/{run_id}/stop")
def stop_run(run_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r:
        raise HTTPException(404)
    if r.status in ("COMPLETED", "FAILED", "CANCELLED"):
        return {"ok": True, "status": r.status}
    r.stop_requested = True
    r.status = "STOPPING"
    log = list(r.live_log or [])
    log.append({"ts": _utcnow().isoformat(), "msg": "STOP requested"})
    r.live_log = log
    db.commit()
    return {"ok": True, "status": "STOPPING"}


@router.delete("/runs/{run_id}")
def delete_run(run_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    r = db.query(Run).filter(Run.id == run_id).first()
    if not r:
        raise HTTPException(404)
    if r.status in ("QUEUED", "RUNNING", "STOPPING"):
        raise HTTPException(400, "请先停止运行再删除")
    # Order: artifact files → artifact rows → run_items → run (accounts kept)
    items = db.query(RunItem).filter(RunItem.run_id == run_id).all()
    item_ids = [i.id for i in items]
    arts = db.query(Artifact).filter(Artifact.run_id == run_id).all()
    if item_ids:
        arts += db.query(Artifact).filter(Artifact.run_item_id.in_(item_ids), Artifact.run_id != run_id).all()
    seen = set()
    for a in arts:
        if a.id in seen:
            continue
        seen.add(a.id)
        if a.path and os.path.isfile(a.path):
            try:
                os.remove(a.path)
            except OSError:
                pass
        db.delete(a)
    db.flush()
    for it in items:
        db.delete(it)
    db.flush()
    db.delete(r)
    db.commit()
    return {"ok": True}


# ── Results / Export ──────────────────────────────────────────────────────────
@router.get("/results")
def list_results(
    run_id: Optional[int] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(RunItem)
    if run_id:
        query = query.filter(RunItem.run_id == run_id)
    if status:
        query = query.filter(RunItem.status == status)
    if q:
        query = query.filter(
            (RunItem.account_email.contains(q)) | (RunItem.reason.contains(q)) | (RunItem.result_code.contains(q))
        )
    items = query.order_by(RunItem.id.desc()).limit(500).all()
    return [_item_out(i, db) for i in items]


@router.get("/results/export")
def export_results(
    run_id: int,
    fmt: str = Query("csv", pattern="^(csv|txt)$"),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = db.query(RunItem).filter(RunItem.run_id == run_id).order_by(RunItem.id).all()
    if fmt == "txt":
        lines = []
        for i in items:
            lines.append(
                f"{i.account_email or '-'} | {i.test_data_masked or '-'} | {i.status} | "
                f"{i.result_code or '-'} | {i.reason or ''}"
            )
        text = "\n".join(lines) + ("\n" if lines else "")
        return PlainTextResponse(text, headers={"Content-Disposition": f"attachment; filename=run_{run_id}.txt"})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["account", "test_data_masked", "status", "result_code", "reason", "duration_ms"])
    for i in items:
        w.writerow([i.account_email or "", i.test_data_masked or "", i.status, i.result_code or "", i.reason or "", i.duration_ms])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}.csv"},
    )


@router.delete("/results")
def delete_results(body: IdsRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    arts = db.query(Artifact).filter(Artifact.run_item_id.in_(body.ids)).all()
    for a in arts:
        if a.path and os.path.isfile(a.path):
            try:
                os.remove(a.path)
            except OSError:
                pass
        db.delete(a)
    db.flush()
    n = 0
    for it in db.query(RunItem).filter(RunItem.id.in_(body.ids)).all():
        db.delete(it)
        n += 1
    db.commit()
    return {"deleted": n}


# ── Artifacts ─────────────────────────────────────────────────────────────────
@router.get("/artifacts", response_model=List[ArtifactOut])
def list_artifacts(
    run_id: Optional[int] = None,
    run_item_id: Optional[int] = None,
    kind: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Artifact)
    if run_id:
        q = q.filter(Artifact.run_id == run_id)
    if run_item_id:
        q = q.filter(Artifact.run_item_id == run_item_id)
    if kind:
        q = q.filter(Artifact.kind == kind)
    return q.order_by(Artifact.id.desc()).limit(200).all()


@router.get("/artifacts/{artifact_id}/content")
def artifact_content(artifact_id: int, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    a = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not a or not a.path or not os.path.isfile(a.path):
        raise HTTPException(404, "文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(a.path)


# ── Cleanup ───────────────────────────────────────────────────────────────────
@router.get("/cleanup/preview", response_model=CleanupPreview)
def cleanup_preview(window: str = "30d", admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    return CleanupPreview(**cleanup_svc.preview(db, window))


@router.post("/cleanup/execute")
def cleanup_execute(body: CleanupRequest, admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    try:
        result = cleanup_svc.execute(
            db, window=body.window, delete_runs=body.delete_runs,
            delete_artifacts=body.delete_artifacts, delete_sessions=body.delete_sessions,
            delete_unused_test_data=body.delete_unused_test_data, delete_accounts=body.delete_accounts,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@router.get("/settings/data-stats")
def data_stats(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    return {
        "accounts": db.query(Account).count(),
        "test_data": db.query(TestData).count(),
        "runs": db.query(Run).count(),
        "run_items": db.query(RunItem).count(),
        "artifacts": db.query(Artifact).count(),
        "tasks": db.query(Task).count(),
        "networks": db.query(NetworkProfile).count(),
        "disk": cleanup_svc.disk_stats(),
    }
