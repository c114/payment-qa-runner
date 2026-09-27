"""Expected vs Actual PASS/FAIL comparison including 3DS rules."""
from __future__ import annotations

from typing import Tuple

# Result codes
SUCCESS = "SUCCESS"
DECLINED = "DECLINED"
INVALID_CARD = "INVALID_CARD"
INVALID_CVV = "INVALID_CVV"
INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
THREEDS = "3DS"
TIMEOUT = "TIMEOUT"
NETWORK_ERROR = "NETWORK_ERROR"
PAGE_ERROR = "PAGE_ERROR"
BROWSER_CRASH = "BROWSER_CRASH"
PROXY_DOWN = "PROXY_DOWN"
CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
UNKNOWN = "UNKNOWN"
CARD_DECLINED = "CARD_DECLINED"
RISK_BLOCK = "RISK_BLOCK"
TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"

# Only these may trigger auto Network Profile switch
NETWORK_SWITCH_ALLOWED = frozenset({NETWORK_ERROR, PROXY_DOWN, CONNECTION_TIMEOUT})
# Alias kept for callers
NETWORK_RETRY_ALLOWED = NETWORK_SWITCH_ALLOWED

# Forbidden to auto-rotate proxy/IP on these
FORBIDDEN_PROXY_ROTATE = frozenset({
    CARD_DECLINED, DECLINED, RISK_BLOCK, TOO_MANY_ATTEMPTS,
    INVALID_CARD, INVALID_CVV, "INVALID_*", THREEDS, INSUFFICIENT_FUNDS,
    "CAPTCHA", "LOGIN_BLOCKED", "BAD_CREDENTIALS", "ACCOUNT_NOT_READY",
})


def normalize_result(code: str) -> str:
    c = (code or UNKNOWN).strip().upper().replace(" ", "_")
    aliases = {
        "PASS": SUCCESS,
        "OK": SUCCESS,
        "APPROVED": SUCCESS,
        "FAIL": DECLINED,
        "FAILED": DECLINED,
        "DECLINE": DECLINED,
        "CARD_DECLINED": DECLINED,
        "THREE_DS": THREEDS,
        "3D_SECURE": THREEDS,
        "3DSECURE": THREEDS,
    }
    return aliases.get(c, c)


def compare_expected_actual(expected: str, actual: str) -> Tuple[str, str, str]:
    """
    Returns (expected_norm, actual_norm, status) where status is PASS|FAIL.
    PASS when Expected == Actual (e.g. DECLINED + DECLINED = PASS).
    3DS actual always yields FAIL unless expected was also 3DS.
    """
    exp = normalize_result(expected)
    act = normalize_result(actual)
    # 3DS detection: Actual=3DS; if Expected != 3DS → FAIL (and case should end immediately)
    if act == THREEDS and exp != THREEDS:
        return exp, act, "FAIL"
    if exp == act:
        return exp, act, "PASS"
    return exp, act, "FAIL"


def may_auto_switch_network(actual: str) -> bool:
    """Only NETWORK_ERROR / PROXY_DOWN / CONNECTION_TIMEOUT may auto-switch Network Profile."""
    return normalize_result(actual) in NETWORK_SWITCH_ALLOWED


def forbid_proxy_rotate_on(actual: str) -> bool:
    act = normalize_result(actual)
    if act in FORBIDDEN_PROXY_ROTATE:
        return True
    if act.startswith("INVALID_"):
        return True
    return False
