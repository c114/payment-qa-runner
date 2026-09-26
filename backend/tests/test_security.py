from app.core.security import (
    encrypt_secret, decrypt_secret, mask_pan, redact_dict, never_persist_cvv, hash_password, verify_password,
)


def test_encryption_roundtrip():
    plain = "SuperSecret_Proxy_Pass!"
    enc = encrypt_secret(plain)
    assert enc != plain
    assert decrypt_secret(enc) == plain


def test_mask_pan():
    assert mask_pan("4111111111111111") == "**** **** **** 1111"
    assert mask_pan("1234") == "**** **** **** 1234"


def test_redaction():
    d = redact_dict({"password": "x", "cvv": "123", "token": "abc", "ok": 1, "pan": "4111111111111111"})
    assert d["password"] == "***REDACTED***"
    assert d["cvv"] == "***REDACTED***"
    assert d["token"] == "***REDACTED***"
    assert d["ok"] == 1
    assert "1111" in d["pan"]


def test_redaction_never_leaks_secrets_plaintext():
    secrets = {
        "password": "PlainPassword123!",
        "card_number": "4111111111111111",
        "cvv": "999",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        "cookie": "session=abc123; Path=/",
        "proxy_password": "ProxySecret!",
        "token": "tok_live_ABCDEF",
        "secret": "super-secret-value",
    }
    out = redact_dict(secrets)
    blob = str(out)
    for plain in secrets.values():
        assert plain not in blob, f"plaintext leaked: {plain}"
    for k in secrets:
        assert out[k] == "***REDACTED***" or (isinstance(out[k], str) and "****" in out[k])


def test_never_persist_cvv():
    assert "cvv" not in never_persist_cvv({"cvv": "123", "name": "a"})
    assert never_persist_cvv({"nested": {"cvc": "9"}})["nested"] == {}


def test_password_hash():
    h = hash_password("Admin123!")
    assert verify_password("Admin123!", h)
