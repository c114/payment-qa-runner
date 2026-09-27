from app.services.importers import preview_accounts, preview_test_data


def test_account_normalize_pipe_and_dash():
    text = """
# comment
email|password
a@example.com|secret1
b@example.com----secret2
  c@example.com | secret3  

invalid-line
d@example.com|secret1
a@example.com|again
"""
    prev = preview_accounts(text, existing_emails=set())
    emails = [l.email for l in prev.lines if l.status == "valid"]
    assert set(emails) == {"a@example.com", "b@example.com", "c@example.com", "d@example.com"}
    assert prev.valid == 4
    assert prev.dupe == 1
    assert prev.error >= 1


def test_account_existing_dupe():
    prev = preview_accounts("a@example.com|x\n", existing_emails={"a@example.com"})
    assert prev.dupe == 1
    assert prev.valid == 0


def test_card_preview_mask_and_dedupe():
    text = """
4242424242424242|12/30|123
4000000000000002|01/28|456
4242424242424242|12/30|999
badcard|xx|1
"""
    prev = preview_test_data(text, existing_last4_expiry=set())
    assert prev.valid == 2
    assert prev.dupe == 1
    assert prev.error >= 1
    for l in prev.lines:
        if l.status == "valid":
            assert l.pan_masked and "****" in l.pan_masked
            assert "123" not in l.raw and "456" not in l.raw
