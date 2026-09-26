from app.services.comparison import (
    compare_expected_actual, may_auto_switch_network, forbid_proxy_rotate_on,
)


def test_declined_vs_declined_pass():
    exp, act, status = compare_expected_actual("DECLINED", "DECLINED")
    assert status == "PASS"


def test_success_vs_declined_fail():
    _, _, status = compare_expected_actual("SUCCESS", "DECLINED")
    assert status == "FAIL"


def test_threeds_fails_unless_expected():
    _, act, status = compare_expected_actual("SUCCESS", "3DS")
    assert act == "3DS" and status == "FAIL"
    _, _, status2 = compare_expected_actual("3DS", "3DS")
    assert status2 == "PASS"


def test_network_switch_policy():
    assert may_auto_switch_network("NETWORK_ERROR")
    assert may_auto_switch_network("PROXY_DOWN")
    assert may_auto_switch_network("CONNECTION_TIMEOUT")
    assert not may_auto_switch_network("DECLINED")
    assert not may_auto_switch_network("3DS")
    assert forbid_proxy_rotate_on("CARD_DECLINED")
    assert forbid_proxy_rotate_on("INVALID_CVV")
    assert forbid_proxy_rotate_on("3DS")
