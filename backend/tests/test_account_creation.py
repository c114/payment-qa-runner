from app.services.account_creation import can_enable_account_creation, is_allowed_test_domain


def test_blocked_domains():
    assert not is_allowed_test_domain("gmail.com")
    assert not is_allowed_test_domain("outlook.com")
    assert not is_allowed_test_domain("yahoo.com")
    assert is_allowed_test_domain("qa.example.com")


def test_enable_requires_domain():
    ok, _ = can_enable_account_creation(True, "gmail.com")
    assert not ok
    ok, _ = can_enable_account_creation(True, "mail.qa-internal.test")
    assert ok
    ok, _ = can_enable_account_creation(False, "")
    assert ok
