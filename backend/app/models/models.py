"""SQLAlchemy models for Payment QA Runner."""
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


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str] = mapped_column(String(512))
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)  # domain allowlist
    env_type: Mapped[str] = mapped_column(String(32), default="sandbox")  # sandbox|staging|internal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PageMapping(Base):
    __tablename__ = "page_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255))
    page_group: Mapped[str] = mapped_column(String(64), default="general")
    selector_type: Mapped[str] = mapped_column(String(32), default="css")  # css|text|playwright|iframe
    selector: Mapped[str] = mapped_column(Text, default="")
    iframe_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_example: Mapped[bool] = mapped_column(Boolean, default=False)
    help_zh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    help_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_key: Mapped[str] = mapped_column(String(64), unique=True)
    name_zh: Mapped[str] = mapped_column(String(128))
    name_en: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))  # navigate|click|fill|wait|detect|screenshot
    mapping_keys: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class QAAccount(Base):
    __tablename__ = "qa_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_enc: Mapped[str] = mapped_column(Text)  # encrypted
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="READY")  # READY|COOLDOWN|DISABLED|BUSY
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Playwright storage_state persistence
    session_status: Mapped[str] = mapped_column(String(32), default="NONE")  # NONE|VALID|EXPIRED
    session_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    session_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountCreationSettings(Base):
    __tablename__ = "account_creation_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    test_email_domain: Mapped[str] = mapped_column(String(255), default="")  # NOT gmail/outlook/yahoo
    name_prefix: Mapped[str] = mapped_column(String(64), default="qa")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Socks5Proxy(Base):
    __tablename__ = "socks5_proxies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    password_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")  # ONLINE|OFFLINE|AUTH_ERROR|TIMEOUT|UNKNOWN
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("host", "port", "username", name="uq_proxy"),)


class NetworkProfile(Base):
    __tablename__ = "network_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    mode: Mapped[str] = mapped_column(String(32), default="direct")  # direct|proxy
    proxy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("socks5_proxies.id"), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    environment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("environments.id"), nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("qa_accounts.id"), nullable=True)
    network_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("network_profiles.id"), nullable=True)
    # CLOSED|OPEN|READY|RUNNING|STALE|ERROR
    status: Mapped[str] = mapped_column(String(32), default="CLOSED")
    worker_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    browser_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # none|starting|ready|running|crashed
    context_state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # none|fresh|active|needs_new
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_action: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)



class TaskPreset(Base):
    """Admin-preconfigured one-click QA tasks for normal users."""
    __tablename__ = "task_presets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    name_zh: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_zh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # smoke | payment_fill | local_fixture
    task_type: Mapped[str] = mapped_column(String(32), default="smoke")
    start_url: Mapped[str] = mapped_column(String(512), default="")
    environment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("environments.id"), nullable=True)
    # production | sandbox | staging | internal | local
    env_scope: Mapped[str] = mapped_column(String(32), default="production")
    # For smoke: never fill card. For payment_fill: requires LIVE_TESTING + sandbox|staging|internal
    allow_card_fill: Mapped[bool] = mapped_column(Boolean, default=False)
    open_add_card_modal: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    payment_test_ref: Mapped[str] = mapped_column(String(128), default="")  # Payrails sandbox card ref
    card_brand: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pan_masked: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # never full PAN
    expiry: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # CVV NEVER stored
    expected_result: Mapped[str] = mapped_column(String(64), default="SUCCESS")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestRun(Base):
    __tablename__ = "test_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id"))
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("qa_accounts.id"), nullable=True)
    network_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("network_profiles.id"), nullable=True)
    proxy_pool_ids: Mapped[list] = mapped_column(JSON, default=list)
    case_ids: Mapped[list] = mapped_column(JSON, default=list)
    run_count: Mapped[str] = mapped_column(String(16), default="1")  # 1|5|10|50|ALL
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")  # QUEUED|RUNNING|PAUSED|STOPPING|STOPPED|COMPLETED|FAILED
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    current_case_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    live_log: Mapped[list] = mapped_column(JSON, default=list)
    # 1.3.0 quick-run / smoke fields
    task_preset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task_presets.id"), nullable=True)
    account_ids: Mapped[list] = mapped_column(JSON, default=list)
    current_account: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    run_mode: Mapped[str] = mapped_column(String(32), default="workflow")  # smoke|payment|workflow|local_fixture
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestResult(Base):
    __tablename__ = "test_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    case_name: Mapped[str] = mapped_column(String(255), default="")
    expected: Mapped[str] = mapped_column(String(64))
    actual: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # PASS|FAIL|ERROR
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    steps: Mapped[list] = mapped_column(JSON, default=list)  # timeline
    screenshot_paths: Mapped[list] = mapped_column(JSON, default=list)
    account_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    network_profile: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pan_masked: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RunnerSettings(Base):
    __tablename__ = "runner_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interval_sec: Mapped[float] = mapped_column(Float, default=5.0)
    timeout_sec: Mapped[float] = mapped_column(Float, default=30.0)
    network_retry: Mapped[int] = mapped_column(Integer, default=2)
    timeout_retry: Mapped[int] = mapped_column(Integer, default=1)
    decline_retry: Mapped[int] = mapped_column(Integer, default=0)  # FORBIDDEN to auto-rotate proxy on decline
    account_failure_threshold: Mapped[int] = mapped_column(Integer, default=3)
    account_cooldown_sec: Mapped[int] = mapped_column(Integer, default=300)
    restart_browser_every_n: Mapped[int] = mapped_column(Integer, default=20)
    max_concurrent_browsers: Mapped[int] = mapped_column(Integer, default=1)
    screenshot_policy: Mapped[str] = mapped_column(String(64), default="FAIL,ERROR,3DS")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SystemSettings(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PayrailsConfig(Base):
    __tablename__ = "payrails_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sandbox_base_url: Mapped[str] = mapped_column(String(512), default="")
    merchant_id: Mapped[str] = mapped_column(String(128), default="")
    # API secrets left blank for admin — never invent fake secrets
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    public_key: Mapped[str] = mapped_column(String(512), default="")
    iframe_selector: Mapped[str] = mapped_column(Text, default="")
    card_number_selector: Mapped[str] = mapped_column(Text, default="")
    expiry_selector: Mapped[str] = mapped_column(Text, default="")
    cvv_selector: Mapped[str] = mapped_column(Text, default="")
    submit_selector: Mapped[str] = mapped_column(Text, default="")
    result_selectors: Mapped[dict] = mapped_column(JSON, default=dict)
    threeds_selectors: Mapped[list] = mapped_column(JSON, default=list)
    sandbox_cards: Mapped[dict] = mapped_column(JSON, default=dict)  # ref -> {pan, expiry, cvv} for fill only
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppLog(Base):
    __tablename__ = "app_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    source: Mapped[str] = mapped_column(String(64), default="api")
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
