"""TXT/CSV parsers for test cases, QA accounts, and SOCKS5 proxies."""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParseResult:
    items: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def _split_row(line: str) -> List[str]:
    """Split a row by | , tab (prefer |) then comma then whitespace for multi-field."""
    if "|" in line:
        return [p.strip() for p in line.split("|")]
    if "\t" in line:
        return [p.strip() for p in line.split("\t")]
    if "," in line:
        # CSV-ish
        try:
            return next(csv.reader(io.StringIO(line)))
        except Exception:
            return [p.strip() for p in line.split(",")]
    return line.split()


def parse_qa_accounts(text: str) -> ParseResult:
    """
    Formats:
      email:password
      email,password
      email\\tpassword
      email password
      email|password
      email----password
      name|email|password
      name|email|password|tag
    Lines starting with # are comments. Header rows are skipped when detected.
    """
    result = ParseResult()
    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        # skip header
        low = line.lower()
        if low.startswith("email") or low.startswith("name|email") or low.startswith("name,email"):
            continue

        email, password, display_name, tag = "", "", None, None

        # email----password (common paste format)
        if "----" in line and "|" not in line:
            parts = [p.strip() for p in line.split("----", 1)]
            if len(parts) == 2 and "@" in parts[0]:
                email, password = parts[0], parts[1]
                if email and password:
                    item = {"email": email, "password": password}
                    if display_name:
                        item["display_name"] = display_name
                    result.items.append(item)
                else:
                    result.errors.append(f"line {i}: missing email/password")
                continue

        # pipe / csv multi-field first
        if "|" in line or ("," in line and line.count(",") >= 2):
            parts = _split_row(line)
            if len(parts) == 2:
                # email|password OR email,password
                a, b = parts[0], parts[1]
                if "@" in a:
                    email, password = a, b
                elif "@" in b:
                    display_name, email, password = a, b, ""
                else:
                    email, password = a, b
            elif len(parts) == 3:
                # name|email|password  OR email|password|tag
                if "@" in parts[0]:
                    email, password, tag = parts[0], parts[1], parts[2]
                else:
                    display_name, email, password = parts[0], parts[1], parts[2]
            elif len(parts) >= 4:
                display_name, email, password, tag = parts[0], parts[1], parts[2], parts[3]
            else:
                result.errors.append(f"Line {i}: unrecognized account format")
                continue
        elif ":" in line and "@" in line.split(":")[0]:
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
        item: Dict[str, Any] = {"email": email, "password": password}
        if display_name:
            item["display_name"] = display_name
        if tag:
            item["tag"] = tag
            item["notes"] = tag
        result.items.append(item)
    return result


def parse_socks5(text: str) -> ParseResult:
    """
    Formats:
      host:port
      host:port:user:pass
      socks5://user:pass@host:port
      host port user pass
      host|port|user|pass
    """
    result = ParseResult()
    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith("host") and ("port" in low):
            continue
        host, port, username, password = "", 0, None, None

        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                host = parts[0]
                try:
                    port = int(parts[1])
                except ValueError:
                    result.errors.append(f"Line {i}: invalid port")
                    continue
                if len(parts) >= 4:
                    username, password = parts[2] or None, parts[3] or None
                elif len(parts) == 3:
                    username = parts[2] or None
            else:
                result.errors.append(f"Line {i}: unrecognized SOCKS5 format")
                continue
        else:
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
    "tag": 7,
    "notes": 8,
}


def parse_test_cases(
    text: str,
    mapping: Optional[Dict[str, int]] = None,
    delimiter: str = "auto",
) -> ParseResult:
    """
    Flexible column mapping. Default:
      case_id | name | payment_test_ref | expected_result | card_brand | pan_last4 | expiry [| tag | notes]
    Delimiters: | , \\t or whitespace. CVV column is ignored if present.
    """
    result = ParseResult()
    mapping = mapping or dict(DEFAULT_CASE_MAPPING)
    cvv_keys = {"cvv", "cvc", "security_code"}

    for i, line in enumerate(_split_lines(text), 1):
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith("case_id") or low.startswith("id|name") or low.startswith("id,name"):
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
        tag = col("tag") or col("tags") or ""
        notes = col("notes") or ""

        item: Dict[str, Any] = {
            "case_id": case_id,
            "name": name,
            "payment_test_ref": col("payment_test_ref") or col("ref") or "",
            "expected_result": expected,
            "card_brand": col("card_brand") or None,
            "pan_masked": pan_masked,
            "expiry": col("expiry") or None,
        }
        tags: List[str] = []
        if tag:
            tags = [t.strip() for t in re.split(r"[,;]", tag) if t.strip()]
        if tags:
            item["tags"] = tags
        if notes:
            item["extra"] = {"notes": notes}
        for ck in cvv_keys:
            if ck in mapping:
                pass  # never store
        result.items.append(item)
    return result


def parse_page_mappings_json(text: str) -> ParseResult:
    """Import page mappings from JSON array or {items:[...]}."""
    result = ParseResult()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        result.errors.append(f"Invalid JSON: {e}")
        return result
    if isinstance(data, dict):
        data = data.get("items") or data.get("mappings") or data.get("page_mappings") or []
    if not isinstance(data, list):
        result.errors.append("Expected JSON array of mappings")
        return result
    for i, row in enumerate(data, 1):
        if not isinstance(row, dict):
            result.errors.append(f"Item {i}: not an object")
            continue
        key = row.get("key") or ""
        if not key:
            result.errors.append(f"Item {i}: missing key")
            continue
        result.items.append({
            "key": key,
            "label": row.get("label") or key,
            "page_group": row.get("page_group") or "general",
            "selector_type": row.get("selector_type") or "css",
            "selector": row.get("selector") or "",
            "iframe_selector": row.get("iframe_selector"),
            "is_example": bool(row.get("is_example", False)),
            "help_zh": row.get("help_zh"),
            "help_en": row.get("help_en"),
            "sort_order": int(row.get("sort_order") or 0),
        })
    return result


def parse_environment_json(text: str) -> ParseResult:
    result = ParseResult()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        result.errors.append(f"Invalid JSON: {e}")
        return result
    if isinstance(data, dict) and "name" in data:
        data = [data]
    if isinstance(data, dict):
        data = data.get("items") or data.get("environments") or []
    if not isinstance(data, list):
        result.errors.append("Expected JSON object or array of environments")
        return result
    for i, row in enumerate(data, 1):
        if not isinstance(row, dict) or not row.get("name") or not row.get("base_url"):
            result.errors.append(f"Item {i}: need name + base_url")
            continue
        env_type = (row.get("env_type") or "sandbox").lower()
        if env_type not in ("sandbox", "staging", "internal"):
            result.errors.append(f"Item {i}: env_type must be sandbox|staging|internal")
            continue
        result.items.append({
            "name": row["name"],
            "base_url": row["base_url"],
            "allowed_domains": list(row.get("allowed_domains") or []),
            "env_type": env_type,
            "is_active": bool(row.get("is_active", True)),
            "notes": row.get("notes"),
        })
    return result


TEMPLATES = {
    "accounts": "# email|password  OR  name|email|password|tag\nqa1@test.local|Secret123\nQA Two|qa2@test.local|Secret456|pool-a\n",
    "proxies": "# host:port  OR  host:port:user:pass  OR  socks5://user:pass@host:port\n127.0.0.1:1080\n10.0.0.1:1080:user:pass\nsocks5://user:pass@10.0.0.2:9050\n",
    "cases": "# case_id|name|payment_test_ref|expected_result|card_brand|pan_last4|expiry|tag|notes\nTC001|Success Visa|SUCCESS_VISA|SUCCESS|visa|4242|12/30|smoke|ok\nTC002|Declined|DECLINED_CARD|DECLINED|visa|0002|12/30|decline|\n",
    "page_mapping": json.dumps([
        {"key": "login.email", "label": "Login Email", "page_group": "login",
         "selector_type": "css", "selector": "input[type=email]", "sort_order": 1}
    ], indent=2) + "\n",
    "environment": json.dumps({
        "name": "Sandbox Example",
        "base_url": "https://sandbox.example.test",
        "allowed_domains": ["sandbox.example.test"],
        "env_type": "sandbox",
        "notes": "example only",
    }, indent=2) + "\n",
}
