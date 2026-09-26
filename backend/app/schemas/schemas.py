"""Pydantic v2 schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EnvironmentIn(BaseModel):
    name: str
    base_url: str
    allowed_domains: List[str] = Field(default_factory=list)
    env_type: str = "sandbox"
    is_active: bool = True
    notes: Optional[str] = None


class EnvironmentOut(EnvironmentIn):
    id: int
    last_test_status: Optional[str] = None
    last_test_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class PageMappingIn(BaseModel):
    key: str
    label: str
    page_group: str = "general"
    selector_type: str = "css"
    selector: str = ""
    iframe_selector: Optional[str] = None
    is_example: bool = False
    help_zh: Optional[str] = None
    help_en: Optional[str] = None
    sort_order: int = 0


class PageMappingOut(PageMappingIn):
    id: int
    model_config = {"from_attributes": True}


class WorkflowStepIn(BaseModel):
    step_key: str
    name_zh: str
    name_en: str
    action: str
    mapping_keys: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0
    enabled: bool = True


class WorkflowStepOut(WorkflowStepIn):
    id: int
    model_config = {"from_attributes": True}


class QAAccountIn(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    notes: Optional[str] = None


class QAAccountOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    status: str
    consecutive_failures: int
    cooldown_until: Optional[datetime] = None
    last_login_status: Optional[str] = None
    last_used_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class Socks5In(BaseModel):
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    label: Optional[str] = None
    is_active: bool = True


class Socks5Out(BaseModel):
    id: int
    host: str
    port: int
    username: Optional[str] = None
    label: Optional[str] = None
    status: str
    latency_ms: Optional[float] = None
    exit_ip: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class NetworkProfileIn(BaseModel):
    name: str
    mode: str = "direct"
    proxy_id: Optional[int] = None
    is_default: bool = False


class NetworkProfileOut(NetworkProfileIn):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


class BrowserSessionIn(BaseModel):
    name: str
    environment_id: Optional[int] = None
    account_id: Optional[int] = None
    network_profile_id: Optional[int] = None


class BrowserSessionOut(BrowserSessionIn):
    id: int
    status: str
    worker_id: Optional[str] = None
    browser_state: Optional[str] = None
    context_state: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    last_action: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TestCaseIn(BaseModel):
    case_id: str
    name: str
    payment_test_ref: str = ""
    card_brand: Optional[str] = None
    pan_masked: Optional[str] = None
    expiry: Optional[str] = None
    expected_result: str = "SUCCESS"
    tags: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class TestCaseOut(TestCaseIn):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


class TestRunCreate(BaseModel):
    name: str = ""
    environment_id: int
    account_id: Optional[int] = None
    network_profile_id: Optional[int] = None
    proxy_pool_ids: List[int] = Field(default_factory=list)
    case_ids: List[str] = Field(default_factory=list)
    run_count: str = "1"


class TestRunOut(BaseModel):
    id: int
    name: str
    environment_id: int
    account_id: Optional[int] = None
    network_profile_id: Optional[int] = None
    proxy_pool_ids: List[int]
    case_ids: List[str]
    run_count: str
    status: str
    progress_done: int
    progress_total: int
    pass_count: int
    fail_count: int
    error_count: int
    current_case_id: Optional[str] = None
    live_log: List[Any] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class TestResultOut(BaseModel):
    id: int
    run_id: int
    case_id: str
    case_name: str
    expected: str
    actual: str
    status: str
    duration_ms: float
    steps: List[Any]
    screenshot_paths: List[str]
    account_email: Optional[str] = None
    network_profile: Optional[str] = None
    error_message: Optional[str] = None
    pan_masked: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class RunnerSettingsIn(BaseModel):
    interval_sec: float = 5.0
    timeout_sec: float = 30.0
    network_retry: int = 2
    timeout_retry: int = 1
    decline_retry: int = 0
    account_failure_threshold: int = 3
    account_cooldown_sec: int = 300
    restart_browser_every_n: int = 20
    max_concurrent_browsers: int = 1
    screenshot_policy: str = "FAIL,ERROR,3DS"


class RunnerSettingsOut(RunnerSettingsIn):
    id: int
    model_config = {"from_attributes": True}


class AccountCreationIn(BaseModel):
    enabled: bool = False
    test_email_domain: str = ""
    name_prefix: str = "qa"


class PayrailsConfigIn(BaseModel):
    sandbox_base_url: str = ""
    merchant_id: str = ""
    api_key: Optional[str] = None  # write-only; blank keeps existing
    public_key: str = ""
    iframe_selector: str = ""
    card_number_selector: str = ""
    expiry_selector: str = ""
    cvv_selector: str = ""
    submit_selector: str = ""
    result_selectors: Dict[str, Any] = Field(default_factory=dict)
    threeds_selectors: List[str] = Field(default_factory=list)
    sandbox_cards: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class PayrailsConfigOut(BaseModel):
    id: int
    sandbox_base_url: str
    merchant_id: str
    has_api_key: bool
    public_key: str
    iframe_selector: str
    card_number_selector: str
    expiry_selector: str
    cvv_selector: str
    submit_selector: str
    result_selectors: Dict[str, Any]
    threeds_selectors: List[str]
    sandbox_cards: Dict[str, Any]
    notes: str
    model_config = {"from_attributes": True}


class ImportMappingIn(BaseModel):
    text: str
    mapping: Optional[Dict[str, int]] = None
    delimiter: str = "auto"


class MessageOut(BaseModel):
    message: str
    detail: Any = None
