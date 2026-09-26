"""Account auto-creation policy — OFF by default; block consumer email domains."""
from __future__ import annotations

BLOCKED_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.jp", "ymail.com", "icloud.com", "me.com",
})


def is_allowed_test_domain(domain: str) -> bool:
    d = (domain or "").strip().lower().lstrip("@")
    if not d or "." not in d:
        return False
    return d not in BLOCKED_EMAIL_DOMAINS


def can_enable_account_creation(enabled: bool, test_email_domain: str) -> tuple[bool, str]:
    if not enabled:
        return True, "disabled"
    if not is_allowed_test_domain(test_email_domain):
        return False, "test_email_domain required and must NOT be gmail/outlook/yahoo/consumer domains"
    return True, "ok"
