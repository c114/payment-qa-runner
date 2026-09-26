"""Real SOCKS5 handshake probe (RFC 1928 + RFC 1929 username/password)."""
from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urlparse


ONLINE = "ONLINE"
AUTH_ERROR = "AUTH_ERROR"
TIMEOUT = "TIMEOUT"
HANDSHAKE_ERROR = "HANDSHAKE_ERROR"
CONNECT_ERROR = "CONNECT_ERROR"
UNKNOWN = "UNKNOWN"

DEFAULT_TARGET = ("1.1.1.1", 80)


@dataclass
class Socks5ProbeResult:
    status: str
    latency_ms: Optional[float] = None
    exit_ip: Optional[str] = None
    detail: str = ""


def parse_proxy_test_target(url_or_hostport: Optional[str]) -> Tuple[str, int]:
    """Extract host:port from PROXY_TEST_URL / admin proxy_test_url."""
    raw = (url_or_hostport or "").strip()
    if not raw:
        return DEFAULT_TARGET
    if "://" not in raw and ":" in raw and raw.count(":") == 1:
        host, port_s = raw.rsplit(":", 1)
        try:
            return host, int(port_s)
        except ValueError:
            return DEFAULT_TARGET
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or DEFAULT_TARGET[0]
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, int(port)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed during SOCKS5 read")
        buf += chunk
    return buf


def build_greeting(methods: bytes = b"\x00\x02") -> bytes:
    """VER=5, NMETHODS, METHODS (0x00 no-auth, 0x02 user/pass)."""
    return bytes([0x05, len(methods)]) + methods


def build_userpass_auth(username: str, password: str) -> bytes:
    """RFC 1929: VER=1, ULEN, UNAME, PLEN, PASSWD."""
    u = (username or "").encode("utf-8")[:255]
    p = (password or "").encode("utf-8")[:255]
    return bytes([0x01, len(u)]) + u + bytes([len(p)]) + p


def build_connect_request(host: str, port: int) -> bytes:
    """CONNECT with ATYP domain (0x03) or IPv4 (0x01)."""
    try:
        packed = socket.inet_aton(host)
        addr = bytes([0x01]) + packed
    except OSError:
        hb = host.encode("idna")
        addr = bytes([0x03, len(hb)]) + hb
    return bytes([0x05, 0x01, 0x00]) + addr + struct.pack("!H", port)


def parse_method_selection(data: bytes) -> int:
    if len(data) < 2 or data[0] != 0x05:
        raise ValueError("invalid method selection")
    return data[1]


def parse_auth_response(data: bytes) -> bool:
    """Return True if auth succeeded (status 0x00)."""
    if len(data) < 2 or data[0] != 0x01:
        raise ValueError("invalid auth response")
    return data[1] == 0x00


def parse_connect_reply(data: bytes) -> int:
    """Return REP code (0 success)."""
    if len(data) < 2 or data[0] != 0x05:
        raise ValueError("invalid connect reply")
    return data[1]


def _read_connect_reply(sock: socket.socket) -> int:
    hdr = _recv_exact(sock, 4)
    rep = parse_connect_reply(hdr)
    atyp = hdr[3]
    if atyp == 0x01:
        _recv_exact(sock, 4 + 2)
    elif atyp == 0x03:
        ln = _recv_exact(sock, 1)[0]
        _recv_exact(sock, ln + 2)
    elif atyp == 0x04:
        _recv_exact(sock, 16 + 2)
    else:
        raise ValueError(f"unknown ATYP {atyp}")
    return rep


def _http_get_via_connected(sock: socket.socket, host: str, path: str = "/", timeout: float = 8.0) -> Tuple[str, Optional[str]]:
    """After SOCKS CONNECT, send a minimal HTTP GET; try to parse body for IP-looking text."""
    sock.settimeout(timeout)
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: payment-qa-socks5-probe/1.1\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    sock.sendall(req)
    chunks: list[bytes] = []
    try:
        while True:
            c = sock.recv(4096)
            if not c:
                break
            chunks.append(c)
            if sum(len(x) for x in chunks) > 65536:
                break
    except socket.timeout:
        pass
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    body = raw.split("\r\n\r\n", 1)[-1] if "\r\n\r\n" in raw else raw
    exit_ip = None
    # Common IP echo services return plain IP
    for line in body.strip().splitlines():
        line = line.strip()
        if line.count(".") == 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in line.split(".")):
            exit_ip = line
            break
    return raw[:500], exit_ip


def probe_socks5(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    test_target: Optional[Tuple[str, int]] = None,
    test_url: Optional[str] = None,
    timeout: float = 8.0,
    fetch_exit_ip: bool = True,
) -> Socks5ProbeResult:
    """
    Full TCP + SOCKS5 greeting + optional user/pass + CONNECT to test target.
    Statuses: ONLINE, AUTH_ERROR, TIMEOUT, HANDSHAKE_ERROR, CONNECT_ERROR.
    """
    target = test_target or parse_proxy_test_target(test_url)
    t_host, t_port = target
    start = time.time()
    sock: Optional[socket.socket] = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)

        # Greeting: offer no-auth + user/pass
        sock.sendall(build_greeting())
        sel = _recv_exact(sock, 2)
        method = parse_method_selection(sel)
        if method == 0xFF:
            return Socks5ProbeResult(HANDSHAKE_ERROR, detail="no acceptable auth method")
        if method == 0x02:
            if not username:
                return Socks5ProbeResult(AUTH_ERROR, detail="server requires username/password")
            sock.sendall(build_userpass_auth(username, password or ""))
            auth_resp = _recv_exact(sock, 2)
            if not parse_auth_response(auth_resp):
                return Socks5ProbeResult(AUTH_ERROR, detail="username/password rejected")
        elif method == 0x00:
            pass
        else:
            return Socks5ProbeResult(HANDSHAKE_ERROR, detail=f"unsupported method {method}")

        sock.sendall(build_connect_request(t_host, t_port))
        rep = _read_connect_reply(sock)
        if rep != 0x00:
            return Socks5ProbeResult(
                CONNECT_ERROR if rep != 0x02 else AUTH_ERROR,
                detail=f"CONNECT REP={rep}",
            )

        latency = (time.time() - start) * 1000
        exit_ip = None
        if fetch_exit_ip:
            try:
                path = "/"
                if test_url and "://" in test_url:
                    path = urlparse(test_url).path or "/"
                    if urlparse(test_url).query:
                        path = path + "?" + urlparse(test_url).query
                _, exit_ip = _http_get_via_connected(sock, t_host, path=path, timeout=timeout)
            except Exception as e:
                # CONNECT succeeded; HTTP probe is optional
                return Socks5ProbeResult(ONLINE, latency_ms=latency, exit_ip=None, detail=f"connect ok; http probe: {e}")

        return Socks5ProbeResult(ONLINE, latency_ms=latency, exit_ip=exit_ip, detail="ok")
    except socket.timeout:
        return Socks5ProbeResult(TIMEOUT, detail="timeout")
    except TimeoutError:
        return Socks5ProbeResult(TIMEOUT, detail="timeout")
    except (OSError, ConnectionError, ValueError, struct.error) as e:
        msg = str(e).lower()
        if "auth" in msg:
            return Socks5ProbeResult(AUTH_ERROR, detail=str(e))
        if "timed out" in msg or "timeout" in msg:
            return Socks5ProbeResult(TIMEOUT, detail=str(e))
        return Socks5ProbeResult(HANDSHAKE_ERROR, detail=str(e))
    except Exception as e:
        return Socks5ProbeResult(UNKNOWN, detail=str(e))
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
