"""JWT auth, password hashing, and Fernet encryption for secrets at rest."""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# Sensitive keys never to log
REDACT_KEYS = frozenset({
    "password", "proxy_password", "cvv", "cvc", "token", "cookie", "cookies",
    "authorization", "secret", "access_token", "refresh_token",
    "card_number", "api_key", "jwt", "bearer",
})


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra: Optional[dict] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.strip()
    if not key:
        # Derive stable Fernet key from JWT secret for local/dev (deploy.sh generates real key)
        digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    # Accept raw Fernet key or derive if invalid length
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        digest = hashlib.sha256(key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt secret (InvalidToken)")
        return ""


def mask_pan(pan: str) -> str:
    """Mask PAN as **** **** **** 1234."""
    digits = "".join(c for c in (pan or "") if c.isdigit())
    if len(digits) < 4:
        return "****"
    return f"**** **** **** {digits[-4:]}"


def redact_value(key: str, value: Any) -> Any:
    k = (key or "").lower()
    if k in REDACT_KEYS or any(x in k for x in ("password", "cvv", "cvc", "token", "cookie", "secret")):
        return "***REDACTED***"
    if k in ("pan", "card_number", "card"):
        return mask_pan(str(value)) if value else value
    return value


def redact_dict(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: redact_dict(redact_value(k, v)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact_dict(x) for x in data]
    return data


def never_persist_cvv(payload: dict) -> dict:
    """Strip CVV/CVC from any dict before persistence."""
    out = {}
    for k, v in payload.items():
        if k.lower() in ("cvv", "cvc", "security_code"):
            continue
        if isinstance(v, dict):
            out[k] = never_persist_cvv(v)
        else:
            out[k] = v
    return out
