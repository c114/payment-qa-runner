"""SQLAlchemy models for Payment Test Runner 2.0.0 — fresh schema, no 1.x compat."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Back-compat alias for deps that historically used AdminUser
AdminUser = Admin


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_enc: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="READY")  # READY|DISABLED|BUSY
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    session_status: Mapped[str] = mapped_column(String(32), default="NONE")  # NONE|VALID|EXPIRED
    session_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    session_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestData(Base):
    __tablename__ = "test_data"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pan_enc: Mapped[str] = mapped_column(Text)  # encrypted full PAN — never expose
    pan_masked: Mapped[str] = mapped_column(String(32))  # **** **** **** 4242
    pan_last4: Mapped[str] = mapped_column(String(4), default="")
    expiry: Mapped[str] = mapped_column(String(16))  # MM/YY
    cvc_enc: Mapped[str] = mapped_column(Text)  # encrypted; never list/export/log
    brand: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="UNUSED")  # UNUSED|USED|INVALID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Production|Sandbox|QA|Staging|Internal
    env_type: Mapped[str] = mapped_column(String(32), default="Sandbox")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    login_url: Mapped[str] = mapped_column(String(512), default="")
    target_url: Mapped[str] = mapped_column(String(512), default="")
    # Derived: only Sandbox/QA/Staging/Internal may fill cards
    allow_card_fill: Mapped[bool] = mapped_column(Boolean, default=False)
    # smoke | card_bind
    task_type: Mapped[str] = mapped_column(String(32), default="smoke")
    # preply_ui | standard_sandbox_binding — worker routes by this
    adapter_type: Mapped[str] = mapped_column(String(64), default="standard_sandbox_binding")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_url_test_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_url_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NetworkProfile(Base):
    __tablename__ = "network_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    protocol: Mapped[str] = mapped_column(String(16), default="direct")  # direct|http|socks5
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    password_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # OK|FAIL
    last_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionRecord(Base):
    """Optional persisted session metadata (storage_state lives on disk)."""
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="NONE")
    path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    task_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # frozen task fields
    network_id: Mapped[Optional[int]] = mapped_column(ForeignKey("network_profiles.id"), nullable=True)
    network_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    account_ids: Mapped[list] = mapped_column(JSON, default=list)
    test_data_ids: Mapped[list] = mapped_column(JSON, default=list)
    # QUEUED|RUNNING|STOPPING|COMPLETED|FAILED|CANCELLED
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0)
    current_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    live_log: Mapped[list] = mapped_column(JSON, default=list)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(16), default="LIVE")  # always LIVE in 2.0
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RunItem(Base):
    __tablename__ = "run_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    account_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test_data_id: Mapped[Optional[int]] = mapped_column(ForeignKey("test_data.id"), nullable=True)
    test_data_masked: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # WAITING|RUNNING|SUCCESS|FAIL|ERROR|CANCELLED
    status: Mapped[str] = mapped_column(String(16), default="WAITING", index=True)
    result_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    state: Mapped[str] = mapped_column(String(64), default="QUEUED")  # state machine step
    steps: Mapped[list] = mapped_column(JSON, default=list)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    run_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("run_items.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))  # screenshot|trace|log
    path: Mapped[str] = mapped_column(String(1024))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
