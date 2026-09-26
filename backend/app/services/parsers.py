"""TXT parsers for test cases, QA accounts, and SOCKS5 proxies."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ParseResult:
    items: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def parse_qa_accounts(text: str) -> ParseResult:
    """
    Formats:
      email:password
      email,password
      email\\tpassword
      email password
    Lines starting with # are comments.
    """
    result = ParseResult()
    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        email, password = "", ""
        if ":" in line and "@" in line.split(":")[0]:
            parts = line.split(":", 1)
            email, password = parts[0].strip(), parts[1].strip()
        elif "\t" in line:
            parts = line.split("\t")
            email, password = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        elif "," in line:
            parts = line.split(",", 1)
            email, password = parts[0].strip(), parts[1].strip()
        else:
            parts = line.split(None, 1)
            email = parts[0]
            password = parts[1] if len(parts) > 1 else ""
        if not email or "@" not in email:
            result.errors.append(f"Line {i}: invalid email")
            continue
        if not password:
            result.errors.append(f"Line {i}: missing password")
            continue
        result.items.append({"email": email, "password": password})
    return result


def parse_socks5(text: str) -> ParseResult:
    """
    Formats:
      host:port
      host:port:user:pass
      socks5://user:pass@host:port
      host port user pass
    """
    result = ParseResult()
    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        host, port, username, password = "", 0, None, None
        m = re.match(
            r"^(?:socks5://)?(?:([^:@]+):([^@]+)@)?([^:\s]+):(\d+)(?::([^:]*):?(.*))?$",
            line.strip(),
            re.I,
        )
        if m:
            user_a, pass_a, host, port_s, user_b, pass_b = m.groups()
            port = int(port_s)
            username = user_a or user_b or None
            password = pass_a or pass_b or None
            if password == "":
                password = None
        else:
            parts = line.replace(",", " ").split()
            if len(parts) >= 2:
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    result.errors.append(f"Line {i}: invalid port")
                    continue
                if len(parts) >= 4:
                    username, password = parts[2], parts[3]
            else:
                result.errors.append(f"Line {i}: unrecognized SOCKS5 format")
                continue
        if not host or not (1 <= port <= 65535):
            result.errors.append(f"Line {i}: invalid host/port")
            continue
        item: Dict[str, Any] = {"host": host, "port": port}
        if username:
            item["username"] = username
        if password:
            item["password"] = password
        result.items.append(item)
    return result


DEFAULT_CASE_MAPPING = {
    "case_id": 0,
    "name": 1,
    "payment_test_ref": 2,
    "expected_result": 3,
    "card_brand": 4,
    "pan_last4": 5,
    "expiry": 6,
}


def parse_test_cases(
    text: str,
    mapping: Optional[Dict[str, int]] = None,
    delimiter: str = "auto",
) -> ParseResult:
    """
    Flexible column mapping. Default:
      case_id | name | payment_test_ref | expected_result | card_brand | pan_last4 | expiry
    Delimiters: | , \\t or whitespace. CVV column is ignored if present.
    """
    result = ParseResult()
    mapping = mapping or dict(DEFAULT_CASE_MAPPING)
    # Never accept CVV into items
    cvv_keys = {"cvv", "cvc", "security_code"}

    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        if delimiter == "auto":
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
            elif "\t" in line:
                parts = [p.strip() for p in line.split("\t")]
            elif "," in line and line.count(",") >= 2:
                parts = [p.strip() for p in line.split(",")]
            else:
                parts = line.split()
        elif delimiter == "|":
            parts = [p.strip() for p in line.split("|")]
        elif delimiter == ",":
            parts = [p.strip() for p in line.split(",")]
        elif delimiter == "\\t" or delimiter == "tab":
            parts = [p.strip() for p in line.split("\t")]
        else:
            parts = line.split()

        def col(key: str) -> str:
            idx = mapping.get(key)
            if idx is None or idx < 0 or idx >= len(parts):
                return ""
            return parts[idx]

        case_id = col("case_id") or f"CASE-{i}"
        name = col("name") or case_id
        expected = (col("expected_result") or "SUCCESS").upper().strip()
        pan_last4 = col("pan_last4") or col("last4") or ""
        pan_masked = f"**** **** **** {pan_last4}" if pan_last4 and pan_last4.isdigit() else None

        item = {
            "case_id": case_id,
            "name": name,
            "payment_test_ref": col("payment_test_ref") or col("ref") or "",
            "expected_result": expected,
            "card_brand": col("card_brand") or None,
            "pan_masked": pan_masked,
            "expiry": col("expiry") or None,
        }
        # Explicitly drop any mapped cvv
        for ck in cvv_keys:
            if ck in mapping:
                pass  # never store
        result.items.append(item)
    return result
