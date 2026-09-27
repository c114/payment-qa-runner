"""Disk/DB cleanup preview + execute."""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import Artifact, Run, RunItem, TestData


def _cutoff(window: str) -> Optional[datetime]:
    now = datetime.now(timezone.utc)
    if window == "7d":
        return now - timedelta(days=7)
    if window == "30d":
        return now - timedelta(days=30)
    return None  # all


def _dir_size(path: str) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def disk_stats() -> dict:
    s = get_settings()
    return {
        "screenshots_bytes": _dir_size(s.screenshot_dir),
        "traces_bytes": _dir_size(os.path.join(os.path.dirname(s.screenshot_dir), "traces"))
        if True else 0,
        "logs_bytes": _dir_size(s.log_dir),
        "sessions_bytes": _dir_size(s.session_dir),
        "reports_bytes": _dir_size(s.report_dir),
    }


def preview(db: Session, window: str = "30d") -> dict:
    s = get_settings()
    cut = _cutoff(window)
    q_runs = db.query(Run)
    if cut:
        q_runs = q_runs.filter(Run.created_at < cut)
    runs = q_runs.all()
    run_ids = [r.id for r in runs]
    items = db.query(RunItem).filter(RunItem.run_id.in_(run_ids)).count() if run_ids else 0
    arts = db.query(Artifact).filter(Artifact.run_id.in_(run_ids)).count() if run_ids else 0
    unused_td = db.query(TestData).filter(TestData.used_count == 0).count()
    stats = disk_stats()
    # traces dir
    traces_dir = os.path.join(os.path.dirname(s.screenshot_dir.rstrip("/")), "traces")
    stats["traces_bytes"] = _dir_size(traces_dir)
    return {
        "window": window,
        "accounts": 0,  # never auto-count for delete
        "test_data": unused_td,
        "runs": len(runs),
        "run_items": items,
        "artifacts": arts,
        **stats,
    }


def _rm_file(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def execute(
    db: Session,
    window: str = "30d",
    delete_runs: bool = True,
    delete_artifacts: bool = True,
    delete_sessions: bool = False,
    delete_unused_test_data: bool = False,
    delete_accounts: bool = False,
) -> dict:
    """Delete Run deletes its results/artifacts but NOT accounts."""
    if delete_accounts:
        raise ValueError("拒绝批量删除账号：请在账号页手动删除")

    cut = _cutoff(window)
    removed = {"runs": 0, "run_items": 0, "artifacts": 0, "files": 0, "test_data": 0, "sessions": 0}

    if delete_runs or delete_artifacts:
        q = db.query(Run)
        if cut:
            q = q.filter(Run.created_at < cut)
        runs = q.all()
        for run in runs:
            arts = db.query(Artifact).filter(Artifact.run_id == run.id).all()
            for a in arts:
                if delete_artifacts or delete_runs:
                    _rm_file(a.path)
                    db.delete(a)
                    removed["artifacts"] += 1
                    removed["files"] += 1
            if delete_runs:
                items = db.query(RunItem).filter(RunItem.run_id == run.id).all()
                for it in items:
                    db.delete(it)
                    removed["run_items"] += 1
                db.delete(run)
                removed["runs"] += 1

    if delete_unused_test_data:
        unused = db.query(TestData).filter(TestData.used_count == 0).all()
        if cut:
            unused = [t for t in unused if t.created_at.replace(tzinfo=timezone.utc) < cut]
        for t in unused:
            db.delete(t)
            removed["test_data"] += 1

    if delete_sessions:
        s = get_settings()
        sess = Path(s.session_dir)
        if sess.is_dir():
            for f in sess.iterdir():
                if f.is_file():
                    try:
                        if cut:
                            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                            if mtime >= cut:
                                continue
                        f.unlink()
                        removed["sessions"] += 1
                        removed["files"] += 1
                    except OSError:
                        pass

    db.commit()
    return removed
