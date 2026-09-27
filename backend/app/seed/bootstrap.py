"""Seed admin, Direct network, Preply Production task, Local Sandbox task."""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.models import Admin, NetworkProfile, Setting, Task

logger = logging.getLogger(__name__)

TASK_FIELD_HELP = {
    "name": {"用途": "任务显示名称", "格式": "文本", "示例": "Preply Payment Page Smoke", "必填": True},
    "description": {"用途": "短描述，首页下拉展示", "格式": "文本", "示例": "生产 UI 冒烟：登录+支付页验证", "必填": False},
    "env_type": {
        "用途": "环境类型；Production 禁止填卡提交",
        "格式": "Production|Sandbox|QA|Staging|Internal",
        "示例": "Sandbox",
        "必填": True,
    },
    "base_url": {"用途": "站点根地址", "格式": "https://…", "示例": "https://preply.com", "必填": True},
    "login_url": {"用途": "登录页（可空，由跳转检测）", "格式": "https://…", "示例": "https://preply.com/login", "必填": False},
    "target_url": {"用途": "支付/目标页", "格式": "https://…", "示例": "https://preply.com/en/settings/payments", "必填": True},
    "task_type": {"用途": "smoke=仅导航验证；card_bind=完整填卡", "格式": "smoke|card_bind", "示例": "card_bind", "必填": True},
}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s[:60] or "task"


def _allow_card(env_type: str) -> bool:
    return env_type in ("Sandbox", "QA", "Staging", "Internal")


def seed_all(db: Session) -> None:
    settings = get_settings()

    # Admin
    if not db.query(Admin).filter(Admin.email == settings.admin_email).first():
        db.add(Admin(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
        logger.info("Seeded admin %s", settings.admin_email)

    # Direct network
    if not db.query(NetworkProfile).filter(NetworkProfile.name == "Direct").first():
        db.add(NetworkProfile(
            name="Direct", protocol="direct", is_default=True,
            last_test_status="OK", last_latency_ms=0,
        ))
        logger.info("Seeded network Direct")

    # Preply Production smoke
    if not db.query(Task).filter(Task.key == "preply-payment-smoke").first():
        db.add(Task(
            key="preply-payment-smoke",
            name="Preply Payment Page Smoke",
            description="生产 UI 冒烟：登录 → Payment methods → Add card 检测。禁止真实填卡提交。",
            env_type="Production",
            base_url="https://preply.com",
            login_url="https://preply.com/login",
            target_url="https://preply.com/en/settings/payments",
            allow_card_fill=False,
            task_type="smoke",
            enabled=True,
            is_builtin=True,
            config={"open_add_card_modal": True},
        ))
        logger.info("Seeded Preply smoke task")

    # Local Sandbox card bind
    sandbox_base = settings.sandbox_base_url or "http://sandbox:8080"
    if not db.query(Task).filter(Task.key == "local-sandbox-bind").first():
        db.add(Task(
            key="local-sandbox-bind",
            name="Local Sandbox Card Binding",
            description="本地沙箱完整绑卡：Login → Payment → Add Card → Fill → Submit → Result。",
            env_type="Sandbox",
            base_url=sandbox_base,
            login_url=f"{sandbox_base}/login",
            target_url=f"{sandbox_base}/settings/payments",
            allow_card_fill=True,
            task_type="card_bind",
            enabled=True,
            is_builtin=True,
            config={"sandbox": True},
        ))
        logger.info("Seeded Local Sandbox task")

    if not db.query(Setting).filter(Setting.key == "app").first():
        db.add(Setting(key="app", value={
            "version": "2.0.0",
            "mode": "LIVE",
            "field_help": TASK_FIELD_HELP,
        }))

    db.commit()


def task_field_help() -> dict:
    return TASK_FIELD_HELP
