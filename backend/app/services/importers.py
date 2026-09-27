"""Account + test-data import: normalize, validate, dedupe, preview."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from app.core.security import mask_pan


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class AccountLine:
    line: int
    raw: str
    status: str  # valid|dupe|error
    reason: str = ""
    email: Optional[str] = None
    password: Optional[str] = None


@dataclass
class AccountPreview:
    total: int = 0
    valid: int = 0
    dupe: int = 0
    error: int = 0
    lines: List[AccountLine] = field(default_factory=list)


@dataclass
class CardLine:
    line: int
    raw: str
    status: str
    reason: str = ""
    pan: Optional[str] = None
    pan_masked: Optional[str] = None
    expiry: Optional[str] = None
    cvc: Optional[str] = None
    brand: Optional[str] = None


@dataclass
class CardPreview:
    total: int = 0
    valid: int = 0
    dupe: int = 0
    error: int = 0
    lines: List[CardLine] = field(default_factory=list)


def _split_lines(text: str) -> List[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _is_header_account(line: str) -> bool:
    low = line.lower().strip()
    return low.startswith("email") or low in ("email|password", "email,password", "email----password")


def _parse_account_row(line: str) -> Tuple[Optional[str], Optional[str], str]:
    """Return (email, password, error_reason)."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None, None, "blank"

    if "----" in s and "|" not in s:
        parts = [p.strip() for p in s.split("----", 1)]
        if len(parts) == 2:
            return parts[0], parts[1], ""
        return None, None, "invalid ---- format"

    if "|" in s:
        parts = [p.strip() for p in s.split("|")]
    elif "\t" in s:
        parts = [p.strip() for p in s.split("\t")]
    elif "," in s:
        try:
            parts = next(csv.reader(io.StringIO(s)))
            parts = [p.strip() for p in parts]
        except Exception:
            parts = [p.strip() for p in s.split(",")]
    elif ":" in s and "@" in s.split(":", 1)[0]:
        parts = [p.strip() for p in s.split(":", 1)]
    else:
        parts = s.split()

    if len(parts) < 2:
        return None, None, "需要 email 与 password"

    # name|email|password
    if len(parts) >= 3 and "@" not in parts[0] and "@" in parts[1]:
        email, password = parts[1], parts[2]
    else:
        email, password = parts[0], parts[1]

    email = email.strip()
    password = password.strip()
    if not email or not password:
        return None, None, "email 或 password 为空"
    if not EMAIL_RE.match(email):
        return None, None, "邮箱格式无效"
    return email.lower(), password, ""


def preview_accounts(text: str, existing_emails: Set[str]) -> AccountPreview:
    preview = AccountPreview()
    seen: Set[str] = set()
    for i, raw in enumerate(_split_lines(text), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _is_header_account(line):
            continue
        preview.total += 1
        email, password, err = _parse_account_row(line)
        if err or not email:
            preview.error += 1
            preview.lines.append(AccountLine(i, raw.rstrip("\n"), "error", err or "解析失败"))
            continue
        if email in existing_emails or email in seen:
            preview.dupe += 1
            preview.lines.append(AccountLine(i, raw.rstrip("\n"), "dupe", "重复账号", email=email, password=password))
            continue
        seen.add(email)
        preview.valid += 1
        preview.lines.append(AccountLine(i, raw.rstrip("\n"), "valid", "", email=email, password=password))
    return preview


def _normalize_expiry(exp: str) -> Optional[str]:
    exp = (exp or "").strip().replace(" ", "")
    m = re.match(r"^(\d{1,2})[/\-](\d{2}|\d{4})$", exp)
    if not m:
        return None
    mm, yy = m.group(1), m.group(2)
    mm_i = int(mm)
    if mm_i < 1 or mm_i > 12:
        return None
    if len(yy) == 4:
        yy = yy[-2:]
    return f"{mm_i:02d}/{yy}"


def _digits(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def _is_header_card(line: str) -> bool:
    low = line.lower().strip()
    return any(low.startswith(h) for h in ("number", "card", "pan", "卡号"))


def _parse_card_row(line: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], str]:
    """Return pan, expiry, cvc, brand, error."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None, None, None, None, "blank"

    if "|" in s:
        parts = [p.strip() for p in s.split("|")]
    elif "\t" in s:
        parts = [p.strip() for p in s.split("\t")]
    elif "," in s:
        try:
            parts = next(csv.reader(io.StringIO(s)))
            parts = [p.strip() for p in parts]
        except Exception:
            parts = [p.strip() for p in s.split(",")]
    else:
        parts = s.split()

    if len(parts) < 3:
        return None, None, None, None, "需要 卡号|有效期|CVC"

    pan = _digits(parts[0])
    expiry = _normalize_expiry(parts[1])
    cvc = _digits(parts[2])
    brand = parts[3].strip() if len(parts) >= 4 and parts[3] else None

    if len(pan) < 13 or len(pan) > 19:
        return None, None, None, None, "卡号位数无效 (13-19)"
    if not expiry:
        return None, None, None, None, "有效期格式无效 (MM/YY)"
    if len(cvc) < 3 or len(cvc) > 4:
        return None, None, None, None, "CVC 位数无效 (3-4)"
    return pan, expiry, cvc, brand, ""


def preview_test_data(text: str, existing_last4_expiry: Set[Tuple[str, str]]) -> CardPreview:
    """Dedupe key: last4+expiry (sufficient for QA sandbox cards without exposing PAN in sets)."""
    preview = CardPreview()
    seen: Set[str] = set()  # full pan hash-ish: pan+expiry
    for i, raw in enumerate(_split_lines(text), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _is_header_card(line):
            continue
        preview.total += 1
        pan, expiry, cvc, brand, err = _parse_card_row(line)
        if err or not pan:
            preview.error += 1
            # Never include CVC in reason/raw echo beyond original raw for preview UI
            safe_raw = raw.rstrip("\n")
            # Mask any long digit runs in raw for display
            safe_raw_disp = re.sub(r"\d{13,19}", lambda m: mask_pan(m.group(0)), safe_raw)
            preview.lines.append(CardLine(i, safe_raw_disp, "error", err or "解析失败"))
            continue
        key = f"{pan}:{expiry}"
        last4 = pan[-4:]
        if key in seen or (last4, expiry) in existing_last4_expiry:
            preview.dupe += 1
            preview.lines.append(CardLine(
                i, mask_pan(pan) + f"|{expiry}|***", "dupe", "重复测试数据",
                pan=pan, pan_masked=mask_pan(pan), expiry=expiry, cvc=cvc, brand=brand,
            ))
            continue
        seen.add(key)
        preview.valid += 1
        preview.lines.append(CardLine(
            i, mask_pan(pan) + f"|{expiry}|***", "valid", "",
            pan=pan, pan_masked=mask_pan(pan), expiry=expiry, cvc=cvc, brand=brand,
        ))
    return preview
