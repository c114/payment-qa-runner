from app.services.parsers import (
    parse_qa_accounts, parse_socks5, parse_test_cases,
    parse_page_mappings_json, parse_environment_json, TEMPLATES,
)


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


def test_parse_qa_accounts_pipe_formats():
    text = """
qa1@test.local|Secret123
QA Two|qa2@test.local|Secret456
Name Three|qa3@test.local|Secret789|pool-a
"""
    r = parse_qa_accounts(text)
    assert len(r.items) == 3
    assert r.items[1]["display_name"] == "QA Two"
    assert r.items[2]["tag"] == "pool-a"
    assert r.items[2]["notes"] == "pool-a"


def test_parse_socks5():
    text = """
127.0.0.1:1080
10.0.0.1:1080:user:pass
socks5://user:pass@10.0.0.2:9050
10.0.0.3|1080|u|p
"""
    r = parse_socks5(text)
    assert len(r.items) == 4
    assert r.items[0]["host"] == "127.0.0.1" and r.items[0]["port"] == 1080
    assert r.items[1]["username"] == "user"
    assert r.items[2]["host"] == "10.0.0.2"
    assert r.items[3]["username"] == "u"


def test_parse_test_cases_no_cvv():
    text = """# id|name|ref|expected|brand|last4|expiry
TC001|Success Visa|SUCCESS_VISA|SUCCESS|visa|4242|12/30
TC002|Declined|DECLINED_CARD|DECLINED|visa|0002|12/30|decline|note
"""
    r = parse_test_cases(text)
    assert len(r.items) == 2
    assert r.items[0]["pan_masked"] == "**** **** **** 4242"
    assert "cvv" not in r.items[0]
    assert r.items[1]["expected_result"] == "DECLINED"
    assert "decline" in r.items[1]["tags"]
    assert r.items[1]["extra"]["notes"] == "note"


def test_errors_keep_line_numbers():
    r = parse_qa_accounts("badline\nqa@x.com:ok")
    assert any(e.startswith("Line 1:") for e in r.errors)
    r2 = parse_socks5("not-a-proxy")
    assert any(e.startswith("Line 1:") for e in r2.errors)


def test_parse_page_mappings_json():
    r = parse_page_mappings_json(TEMPLATES["page_mapping"])
    assert len(r.items) == 1
    assert r.items[0]["key"] == "login.email"


def test_parse_environment_json():
    r = parse_environment_json(TEMPLATES["environment"])
    assert len(r.items) == 1
    assert r.items[0]["env_type"] == "sandbox"


def test_templates_exist():
    for k in ("accounts", "proxies", "cases", "page_mapping", "environment"):
        assert k in TEMPLATES and TEMPLATES[k]
