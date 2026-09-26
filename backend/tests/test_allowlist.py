import pytest
from app.services.allowlist import is_url_allowed, assert_navigation_allowed, extract_host


def test_allowlist_exact_and_subdomain():
    allowed = ["qa.example.com"]
    assert is_url_allowed("https://qa.example.com/path", allowed)
    assert is_url_allowed("https://app.qa.example.com/", allowed)
    assert not is_url_allowed("https://evil.com/", allowed)
    assert not is_url_allowed("https://preply.com/", allowed)


def test_empty_allowlist_fail_closed():
    assert not is_url_allowed("https://anything.com", [])


def test_assert_raises():
    with pytest.raises(PermissionError):
        assert_navigation_allowed("https://preply.com", ["sandbox.local"])


def test_extract_host():
    assert extract_host("https://WWW.Example.COM/x") == "example.com"
