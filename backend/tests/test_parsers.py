from app.services.parsers import parse_qa_accounts, parse_socks5, parse_test_cases


def test_parse_qa_accounts():
    text = """# comment
qa1@test.local:Secret123
qa2@test.local,Secret456
qa3@test.local\tSecret789
"""
    r = parse_qa_accounts(text)
    assert len(r.items) == 3
    assert r.items[0]["email"] == "qa1@test.local"
    assert r.items[0]["password"] == "Secret123"
    assert not r.errors


def test_parse_socks5():
    text = """
127.0.0.1:1080
10.0.0.1:1080:user:pass
socks5://user:pass@10.0.0.2:9050
"""
    r = parse_socks5(text)
    assert len(r.items) == 3
    assert r.items[0]["host"] == "127.0.0.1" and r.items[0]["port"] == 1080
    assert r.items[1]["username"] == "user"
    assert r.items[2]["host"] == "10.0.0.2"


def test_parse_test_cases_no_cvv():
    text = """# id|name|ref|expected|brand|last4|expiry
TC001|Success Visa|SUCCESS_VISA|SUCCESS|visa|4242|12/30
TC002|Declined|DECLINED_CARD|DECLINED|visa|0002|12/30
"""
    r = parse_test_cases(text)
    assert len(r.items) == 2
    assert r.items[0]["pan_masked"] == "**** **** **** 4242"
    assert "cvv" not in r.items[0]
    assert r.items[1]["expected_result"] == "DECLINED"


def test_errors_keep_line_numbers():
    r = parse_qa_accounts("badline\nqa@x.com:ok")
    assert any(e.startswith("Line 1:") for e in r.errors)
    r2 = parse_socks5("not-a-proxy")
    assert any(e.startswith("Line 1:") for e in r2.errors)
