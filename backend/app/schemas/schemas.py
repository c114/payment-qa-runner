"""Pydantic schemas for Payment Test Runner 2.0.0."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminOut(BaseModel):
    id: int
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Accounts ──────────────────────────────────────────────────────────────────
class AccountOut(BaseModel):
    id: int
    email: str
    status: str
    selected: bool
    session_status: str
    last_result: Optional[str] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportPreviewRequest(BaseModel):
    text: str = ""


class ImportConfirmRequest(BaseModel):
    text: str = ""
    skip_dupes: bool = True


class ImportLineResult(BaseModel):
    line: int
    raw: str
    status: str  # valid|dupe|error
    reason: str = ""
    email: Optional[str] = None


class ImportPreviewResponse(BaseModel):
    total: int
    valid: int
    dupe: int
    error: int
    lines: List[ImportLineResult]


class SelectRequest(BaseModel):
    ids: List[int]
    selected: bool = True


class IdsRequest(BaseModel):
    ids: List[int]


# ── Test Data ─────────────────────────────────────────────────────────────────
class TestDataOut(BaseModel):
    id: int
    pan_masked: str
    pan_last4: str
    expiry: str
    brand: Optional[str] = None
    selected: bool
    used_count: int
    status: str
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestDataImportLine(BaseModel):
    line: int
    raw: str
    status: str
    reason: str = ""
    pan_masked: Optional[str] = None
    expiry: Optional[str] = None


class TestDataImportPreview(BaseModel):
    total: int
    valid: int
    dupe: int
    error: int
    lines: List[TestDataImportLine]


# ── Tasks ─────────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    env_type: str = Field(..., pattern="^(Production|Sandbox|QA|Staging|Internal)$")
    base_url: str = Field(..., min_length=1)
    login_url: str = ""
    target_url: str = Field(..., min_length=1)
    task_type: str = "smoke"  # smoke|card_bind
    enabled: bool = True
    key: Optional[str] = None
    config: dict = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    env_type: Optional[str] = None
    base_url: Optional[str] = None
    login_url: Optional[str] = None
    target_url: Optional[str] = None
    task_type: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None


class TaskOut(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    env_type: str
    base_url: str
    login_url: str
    target_url: str
    allow_card_fill: bool
    task_type: str
    enabled: bool
    is_builtin: bool
    config: dict = Field(default_factory=dict)
    last_url_test_status: Optional[str] = None
    last_url_test_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    field_help: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


# ── Networks ──────────────────────────────────────────────────────────────────
class NetworkCreate(BaseModel):
    name: str
    protocol: str = Field(..., pattern="^(direct|http|socks5)$")
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_default: bool = False


class NetworkUpdate(BaseModel):
    name: Optional[str] = None
    protocol: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_default: Optional[bool] = None


class NetworkOut(BaseModel):
    id: int
    name: str
    protocol: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    has_password: bool = False
    is_default: bool
    last_test_status: Optional[str] = None
    last_latency_ms: Optional[float] = None
    last_test_error: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Runs ──────────────────────────────────────────────────────────────────────
class RunCreate(BaseModel):
    task_id: int
    network_id: Optional[int] = None
    account_ids: Optional[List[int]] = None  # None → use selected
    test_data_ids: Optional[List[int]] = None


class RunItemOut(BaseModel):
    id: int
    run_id: int
    account_id: Optional[int] = None
    account_email: Optional[str] = None
    test_data_id: Optional[int] = None
    test_data_masked: Optional[str] = None
    status: str
    result_code: Optional[str] = None
    reason: Optional[str] = None
    state: str
    steps: list = Field(default_factory=list)
    duration_ms: float = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunOut(BaseModel):
    id: int
    task_id: int
    task_snapshot: dict = Field(default_factory=dict)
    network_id: Optional[int] = None
    network_snapshot: dict = Field(default_factory=dict)
    account_ids: list = Field(default_factory=list)
    test_data_ids: list = Field(default_factory=list)
    status: str
    progress_done: int
    progress_total: int
    success_count: int
    fail_count: int
    error_count: int
    cancelled_count: int
    current_account: Optional[str] = None
    current_step: Optional[str] = None
    live_log: list = Field(default_factory=list)
    stop_requested: bool = False
    mode: str = "LIVE"
    error_code: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    items: Optional[List[RunItemOut]] = None

    model_config = ConfigDict(from_attributes=True)


class ArtifactOut(BaseModel):
    id: int
    run_id: int
    run_item_id: Optional[int] = None
    kind: str
    path: str
    meta: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Cleanup / Health / Home ───────────────────────────────────────────────────
class CleanupPreview(BaseModel):
    window: str  # 7d|30d|all
    accounts: int = 0
    test_data: int = 0
    runs: int = 0
    run_items: int = 0
    artifacts: int = 0
    screenshots_bytes: int = 0
    traces_bytes: int = 0
    logs_bytes: int = 0
    sessions_bytes: int = 0


class CleanupRequest(BaseModel):
    window: str = "30d"
    delete_runs: bool = True
    delete_artifacts: bool = True
    delete_sessions: bool = False
    delete_unused_test_data: bool = False
    delete_accounts: bool = False  # dangerous; default off


class HealthOut(BaseModel):
    status: str
    version: str
    mode: str
    backend: str
    database: str
    worker: str
    chromium: str
    network: str
    disk: dict = Field(default_factory=dict)
    detail: dict = Field(default_factory=dict)


class ReadinessOut(BaseModel):
    ready: bool
    reasons: List[str] = Field(default_factory=list)
    accounts_imported: int = 0
    accounts_selected: int = 0
    test_data_imported: int = 0
    test_data_available: int = 0
    test_data_selected: int = 0
    max_executable: int = 0
    task: Optional[TaskOut] = None
    network: Optional[NetworkOut] = None
    checklist: dict = Field(default_factory=dict)
