"""finish_item status/state mapping."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.runner import finish_item


def _item():
    return SimpleNamespace(
        result_code=None, reason=None, steps=None, duration_ms=0,
        finished_at=None, status="RUNNING", state="FILLING",
    )


def _run():
    return SimpleNamespace(
        cancelled_count=0, success_count=0, fail_count=0, error_count=0, progress_done=0,
    )


def test_fail_declined_is_completed_not_error():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "FAIL/DECLINED", "declined", [], time.monotonic())
    assert item.status == "FAIL"
    assert item.state == "COMPLETED"
    assert run.fail_count == 1
    assert run.error_count == 0


def test_fail_3ds_completed():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "FAIL/3DS_REQUIRED", "3ds", [], time.monotonic())
    assert item.status == "FAIL"
    assert item.state == "COMPLETED"


def test_fail_invalid_completed():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "FAIL/INVALID_DATA", "bad", [], time.monotonic())
    assert item.status == "FAIL"
    assert item.state == "COMPLETED"


def test_success_bound():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "SUCCESS/BOUND", "ok", [], time.monotonic())
    assert item.status == "SUCCESS"
    assert item.state == "COMPLETED"


def test_technical_error():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "ERROR/BROWSER_ERROR", "boom", [], time.monotonic())
    assert item.status == "ERROR"
    assert item.state == "ERROR"


def test_cancelled():
    db = MagicMock()
    item, run = _item(), _run()
    finish_item(db, run, item, None, "CANCELLED", "stop", [], time.monotonic())
    assert item.status == "CANCELLED"
    assert item.state == "CANCELLED"
