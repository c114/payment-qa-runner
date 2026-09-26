"""Domain allowlist enforcement for browser navigation."""
from __future__ import annotations

from typing import Iterable, List, Sequence
from urllib.parse import urlparse


def normalize_domain(host: str) -> str:
    h = (host or "").strip().lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def extract_host(url: str) -> str:
    if not url:
        return ""
    raw = url.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    return normalize_domain(parsed.hostname or "")


def is_url_allowed(url: str, allowed_domains: Sequence[str]) -> bool:
    """
    Return True if URL host matches allowlist (exact or subdomain).
    Empty allowlist → refuse all (fail closed).
    """
    if not allowed_domains:
        return False
    host = extract_host(url)
    if not host:
        return False
    allowed = [normalize_domain(d) for d in allowed_domains if d]
    for d in allowed:
        if host == d or host.endswith("." + d):
            return True
    return False


def assert_navigation_allowed(url: str, allowed_domains: Sequence[str]) -> None:
    if not is_url_allowed(url, allowed_domains):
        raise PermissionError(
            f"Navigation refused: '{url}' is outside allowed_domains {list(allowed_domains)}"
        )


def validate_environment_url(base_url: str, env_type: str) -> List[str]:
    """Soft warnings for production-looking hosts — do not hardcode preply.com as default."""
    warnings = []
    host = extract_host(base_url)
    if env_type not in ("sandbox", "staging", "internal"):
        warnings.append("env_type should be sandbox|staging|internal")
    if host in ("preply.com", "www.preply.com"):
        warnings.append(
            "preply.com is UI reference only — do not use live production as default Environment"
        )
    return warnings
