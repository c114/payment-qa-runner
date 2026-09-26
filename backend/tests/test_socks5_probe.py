"""Unit tests for SOCKS5 handshake helpers and auth failure parsing."""
from __future__ import annotations

import socket
import threading
from typing import Callable

import pytest

from app.services.socks5_probe import (
    AUTH_ERROR, HANDSHAKE_ERROR, ONLINE, TIMEOUT,
    build_connect_request, build_greeting, build_userpass_auth,
    parse_auth_response, parse_method_selection, parse_proxy_test_target,
    probe_socks5,
)


def test_parse_proxy_test_target_defaults():
    assert parse_proxy_test_target(None) == ("1.1.1.1", 80)
    assert parse_proxy_test_target("10.0.0.1:9050") == ("10.0.0.1", 9050)
    host, port = parse_proxy_test_target("http://example.com/path")
    assert host == "example.com" and port == 80


def test_greeting_and_auth_builders():
    g = build_greeting()
    assert g[0] == 0x05 and g[1] == 2 and 0x00 in g[2:] and 0x02 in g[2:]
    auth = build_userpass_auth("user", "pass")
    assert auth[0] == 0x01 and auth[1] == 4  # len('user')
    assert parse_auth_response(bytes([0x01, 0x00])) is True
    assert parse_auth_response(bytes([0x01, 0x01])) is False
    assert parse_method_selection(bytes([0x05, 0x02])) == 0x02


def test_connect_request_ipv4():
    req = build_connect_request("1.1.1.1", 80)
    assert req[0:3] == bytes([0x05, 0x01, 0x00])
    assert req[3] == 0x01


def _serve_once(handler: Callable[[socket.socket], None], port_holder: list) -> threading.Thread:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])

    def run():
        try:
            conn, _ = srv.accept()
            with conn:
                handler(conn)
        finally:
            srv.close()

    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th


def test_auth_failure_via_mock_server():
    port_holder: list = []

    def handler(conn: socket.socket):
        # read greeting
        conn.recv(16)
        conn.sendall(bytes([0x05, 0x02]))  # require user/pass
        conn.recv(64)
        conn.sendall(bytes([0x01, 0x01]))  # auth fail

    _serve_once(handler, port_holder)
    r = probe_socks5("127.0.0.1", port_holder[0], username="u", password="bad", fetch_exit_ip=False, timeout=2)
    assert r.status == AUTH_ERROR


def test_handshake_error_no_methods():
    port_holder: list = []

    def handler(conn: socket.socket):
        conn.recv(16)
        conn.sendall(bytes([0x05, 0xFF]))

    _serve_once(handler, port_holder)
    r = probe_socks5("127.0.0.1", port_holder[0], fetch_exit_ip=False, timeout=2)
    assert r.status == HANDSHAKE_ERROR


def test_timeout_closed_port():
    # Connect to a blackhole / closed port quickly — use unlikely high port with short timeout
    r = probe_socks5("127.0.0.1", 1, fetch_exit_ip=False, timeout=0.3)
    assert r.status in (TIMEOUT, HANDSHAKE_ERROR, "CONNECT_ERROR", "UNKNOWN")
