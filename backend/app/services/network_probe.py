"""Network profile connectivity probe (direct / HTTP / SOCKS5)."""
from __future__ import annotations

import socket
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings


def probe_direct(timeout: float = 8.0) -> Tuple[bool, float, str]:
    settings = get_settings()
    url = settings.proxy_test_url or "http://1.1.1.1/"
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            latency = (time.monotonic() - t0) * 1000
            if r.status_code < 500:
                return True, round(latency, 1), ""
            return False, round(latency, 1), f"HTTP {r.status_code}"
    except Exception as e:
        return False, round((time.monotonic() - t0) * 1000, 1), str(e)[:200]


def probe_http_proxy(
    host: str, port: int, username: Optional[str] = None, password: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[bool, float, str]:
    settings = get_settings()
    url = settings.proxy_test_url or "http://1.1.1.1/"
    if username:
        proxy = f"http://{username}:{password or ''}@{host}:{port}"
    else:
        proxy = f"http://{host}:{port}"
    t0 = time.monotonic()
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            latency = (time.monotonic() - t0) * 1000
            if r.status_code < 500:
                return True, round(latency, 1), ""
            return False, round(latency, 1), f"HTTP {r.status_code}"
    except Exception as e:
        return False, round((time.monotonic() - t0) * 1000, 1), str(e)[:200]


def probe_socks5(
    host: str, port: int, username: Optional[str] = None, password: Optional[str] = None,
    timeout: float = 10.0,
) -> Tuple[bool, float, str]:
    """TCP connect + optional httpx SOCKS proxy if httpx[socks] available; else TCP-only."""
    t0 = time.monotonic()
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
    except Exception as e:
        return False, round((time.monotonic() - t0) * 1000, 1), f"TCP connect failed: {e}"[:200]

    settings = get_settings()
    url = settings.proxy_test_url or "http://1.1.1.1/"
    if username:
        proxy = f"socks5://{username}:{password or ''}@{host}:{port}"
    else:
        proxy = f"socks5://{host}:{port}"
    try:
        with httpx.Client(proxy=proxy, timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            latency = (time.monotonic() - t0) * 1000
            if r.status_code < 500:
                return True, round(latency, 1), ""
            return False, round(latency, 1), f"HTTP {r.status_code}"
    except Exception as e:
        # TCP OK but HTTP via SOCKS failed — still report partial
        latency = (time.monotonic() - t0) * 1000
        msg = str(e)
        if "socks" in msg.lower() or "proxy" in msg.lower() or "No package" in msg:
            return True, round(latency, 1), "TCP OK (SOCKS HTTP probe skipped)"
        return False, round(latency, 1), msg[:200]


def probe_profile(
    protocol: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Tuple[bool, float, str]:
    proto = (protocol or "direct").lower()
    if proto == "direct":
        return probe_direct()
    if not host or not port:
        return False, 0.0, "缺少 host/port"
    if proto == "http":
        return probe_http_proxy(host, port, username, password)
    if proto == "socks5":
        return probe_socks5(host, port, username, password)
    return False, 0.0, f"未知协议: {protocol}"
