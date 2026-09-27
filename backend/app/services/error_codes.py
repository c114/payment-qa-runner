"""Standardized error codes + Chinese UI messages for Payment QA Runner 1.3.0."""
from __future__ import annotations

from typing import Dict, Optional

# Live / environment
LIVE_TESTING_DISABLED = "LIVE_TESTING_DISABLED"
ENVIRONMENT_NOT_ALLOWED = "ENVIRONMENT_NOT_ALLOWED"
ENVIRONMENT_MISSING = "ENVIRONMENT_MISSING"
ALLOWLIST_REFUSED = "ALLOWLIST_REFUSED"

# Account / auth
ACCOUNT_NOT_READY = "ACCOUNT_NOT_READY"
ACCOUNT_MISSING = "ACCOUNT_MISSING"
AUTH_REQUIRED = "AUTH_REQUIRED"
BAD_CREDENTIALS = "BAD_CREDENTIALS"
CAPTCHA = "CAPTCHA"
LOGIN_BLOCKED = "LOGIN_BLOCKED"
SESSION_EXPIRED = "SESSION_EXPIRED"

# Page / network
TARGET_PAGE_READY = "TARGET_PAGE_READY"
PAGE_ERROR = "PAGE_ERROR"
NETWORK_ERROR = "NETWORK_ERROR"
TIMEOUT = "TIMEOUT"
CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
PROXY_DOWN = "PROXY_DOWN"
BROWSER_CRASH = "BROWSER_CRASH"

# Smoke / payment policy
CARD_FILL_FORBIDDEN = "CARD_FILL_FORBIDDEN"
PAYMENT_FILL_NOT_ALLOWED = "PAYMENT_FILL_NOT_ALLOWED"
TASK_NOT_FOUND = "TASK_NOT_FOUND"
MOCK_MODE = "MOCK_MODE"
UNKNOWN = "UNKNOWN"

MESSAGES_ZH: Dict[str, str] = {
    LIVE_TESTING_DISABLED: "实时浏览器测试未启用（LIVE_TESTING_ENABLED=false）。不会回退到 Mock。",
    ENVIRONMENT_NOT_ALLOWED: "当前环境不允许此操作（生产仅限 UI Smoke，填卡需沙箱/预发/内网）。",
    ENVIRONMENT_MISSING: "未找到环境配置。",
    ALLOWLIST_REFUSED: "目标 URL 不在域名白名单内，已拒绝导航。",
    ACCOUNT_NOT_READY: "账号未就绪或缺失。请先导入已有测试账号（不支持自动注册）。",
    ACCOUNT_MISSING: "未选择测试账号。",
    AUTH_REQUIRED: "需要登录。",
    BAD_CREDENTIALS: "账号或密码错误。",
    CAPTCHA: "遇到验证码，已停止（不会轮换 IP）。",
    LOGIN_BLOCKED: "登录被拦截，已停止（不会轮换 IP）。",
    SESSION_EXPIRED: "会话已过期，将重新登录。",
    TARGET_PAGE_READY: "目标支付页已就绪（Payment methods + Add card）。",
    PAGE_ERROR: "页面错误。",
    NETWORK_ERROR: "网络错误。",
    TIMEOUT: "超时。",
    CONNECTION_TIMEOUT: "连接超时。",
    PROXY_DOWN: "代理不可用。",
    BROWSER_CRASH: "浏览器崩溃。",
    CARD_FILL_FORBIDDEN: "生产 Smoke 禁止填写卡号/CVV/提交。",
    PAYMENT_FILL_NOT_ALLOWED: "填卡工作流需要 LIVE_TESTING_ENABLED 且环境为 sandbox|staging|internal。",
    TASK_NOT_FOUND: "任务预设不存在或未启用。",
    MOCK_MODE: "当前为 Mock 模式，结果不是真实浏览器 PASS。",
    UNKNOWN: "未知错误。",
}

MESSAGES_EN: Dict[str, str] = {
    LIVE_TESTING_DISABLED: "Live browser testing is disabled. Will not fall back to mock.",
    ENVIRONMENT_NOT_ALLOWED: "Environment does not allow this action.",
    ENVIRONMENT_MISSING: "Environment not found.",
    ALLOWLIST_REFUSED: "URL outside domain allowlist.",
    ACCOUNT_NOT_READY: "Account not ready. Import existing accounts (no auto Sign up).",
    ACCOUNT_MISSING: "No account selected.",
    AUTH_REQUIRED: "Authentication required.",
    BAD_CREDENTIALS: "Bad credentials.",
    CAPTCHA: "CAPTCHA encountered — stopped (no IP rotate).",
    LOGIN_BLOCKED: "Login blocked — stopped (no IP rotate).",
    SESSION_EXPIRED: "Session expired — will re-login once.",
    TARGET_PAGE_READY: "Payment methods page ready.",
    PAGE_ERROR: "Page error.",
    NETWORK_ERROR: "Network error.",
    TIMEOUT: "Timeout.",
    CONNECTION_TIMEOUT: "Connection timeout.",
    PROXY_DOWN: "Proxy down.",
    BROWSER_CRASH: "Browser crash.",
    CARD_FILL_FORBIDDEN: "Production smoke forbids card fill/submit.",
    PAYMENT_FILL_NOT_ALLOWED: "Card fill requires LIVE_TESTING_ENABLED + sandbox|staging|internal.",
    TASK_NOT_FOUND: "Task preset not found.",
    MOCK_MODE: "Mock mode — results are not live PASS.",
    UNKNOWN: "Unknown error.",
}

# Codes that must NEVER trigger proxy/IP rotation
NO_PROXY_ROTATE = frozenset({
    BAD_CREDENTIALS, CAPTCHA, LOGIN_BLOCKED, ACCOUNT_NOT_READY,
    "DECLINED", "CARD_DECLINED", "3DS", "INVALID_CARD", "INVALID_CVV",
    "INSUFFICIENT_FUNDS", "RISK_BLOCK", "TOO_MANY_ATTEMPTS",
})

# Only these may auto-retry with network switch
NETWORK_RETRY_ALLOWED = frozenset({NETWORK_ERROR, CONNECTION_TIMEOUT, PROXY_DOWN})


def message_zh(code: Optional[str]) -> str:
    if not code:
        return MESSAGES_ZH[UNKNOWN]
    return MESSAGES_ZH.get(code, code)


def message_en(code: Optional[str]) -> str:
    if not code:
        return MESSAGES_EN[UNKNOWN]
    return MESSAGES_EN.get(code, code)


def ui_payload(code: str, detail: str = "") -> dict:
    return {
        "error_code": code,
        "message_zh": message_zh(code),
        "message_en": message_en(code),
        "detail": detail or "",
    }
