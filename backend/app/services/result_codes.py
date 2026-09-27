"""Canonical result codes for Payment Test Runner 2.0.0."""
from __future__ import annotations

SUCCESS_BOUND = "SUCCESS/BOUND"
FAIL_DECLINED = "FAIL/DECLINED"
FAIL_3DS = "FAIL/3DS_REQUIRED"
FAIL_INVALID = "FAIL/INVALID_DATA"
ERROR_BAD_CREDENTIALS = "ERROR/BAD_CREDENTIALS"
ERROR_LOGIN_TIMEOUT = "ERROR/LOGIN_TIMEOUT"
ERROR_NETWORK = "ERROR/NETWORK_ERROR"
ERROR_TARGET = "ERROR/TARGET_NOT_FOUND"
ERROR_BROWSER = "ERROR/BROWSER_ERROR"
ERROR_UNKNOWN = "ERROR/UNKNOWN_RESULT"
ERROR_CANCELLED = "CANCELLED"

# High-level bucket
def bucket(code: str | None) -> str:
    if not code:
        return "ERROR"
    if code.startswith("SUCCESS"):
        return "SUCCESS"
    if code.startswith("FAIL"):
        return "FAIL"
    if code == "CANCELLED":
        return "CANCELLED"
    return "ERROR"


def never_unknown_as_success(code: str | None) -> str:
    """Unknown / empty → ERROR/UNKNOWN_RESULT. Never SUCCESS."""
    if not code:
        return ERROR_UNKNOWN
    c = code.strip().upper()
    if c in ("PASS", "OK", "SUCCESS", "SUCCESS/PASS"):
        # ambiguous bare SUCCESS without BOUND still allowed only if explicit SUCCESS/BOUND
        if code.strip() == SUCCESS_BOUND or code.strip().upper() == "SUCCESS/BOUND":
            return SUCCESS_BOUND
        if code.strip().upper().startswith("SUCCESS/"):
            return code.strip()
        return ERROR_UNKNOWN
    known = {
        SUCCESS_BOUND, FAIL_DECLINED, FAIL_3DS, FAIL_INVALID,
        ERROR_BAD_CREDENTIALS, ERROR_LOGIN_TIMEOUT, ERROR_NETWORK,
        ERROR_TARGET, ERROR_BROWSER, ERROR_UNKNOWN, ERROR_CANCELLED,
    }
    if code.strip() in known:
        return code.strip()
    # Allow custom FAIL/* and ERROR/* but never invent SUCCESS
    if code.startswith("FAIL/") or code.startswith("ERROR/"):
        return code
    if code.startswith("SUCCESS/"):
        return code
    return ERROR_UNKNOWN


# State machine steps
STATES = [
    "QUEUED",
    "STARTING_BROWSER",
    "NAVIGATING",
    "WAITING_PAGE",
    "AUTH_REQUIRED",
    "AUTHENTICATING",
    "AUTH_SUCCESS",
    "TARGET_LOADING",
    "TARGET_READY",
    "FORM_OPEN",
    "FILLING",
    "SUBMITTING",
    "WAITING_RESULT",
    "COMPLETED",
    "ERROR",
    "CANCELLED",
]
