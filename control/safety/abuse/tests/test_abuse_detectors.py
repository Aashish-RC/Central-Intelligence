"""
Tests for Abuse & Misuse Detectors (10.48, 10.49, 10.50)
Verifies multi-account creation detection, quota gaming / disposable email detection,
and automated script / high-RPM flooder blocking.
"""

import time
import pytest
from control.safety.abuse.multi_account_detector import (
    MultiAccountDetector,
    default_multi_account_detector,
)
from control.safety.abuse.quota_gaming_detector import (
    QuotaGamingDetector,
)
from control.safety.abuse.automated_misuse_detector import (
    AutomatedMisuseDetector,
)
from control.identity.lifecycle.account_manager import AccountLifecycleManager


def test_fifth_account_from_same_ip_flagged():
    """Acceptance Test: 5th account from same IP is flagged (Feature 10.48)."""
    detector = MultiAccountDetector(ip_threshold=5)
    ip = "198.51.100.42"

    # Accounts 1 to 4 should be allowed without flag
    for i in range(1, 5):
        res = detector.record_and_evaluate(
            user_id=f"user_{i}",
            email=f"user_{i}@example.com",
            ip_address=ip,
        )
        assert res.is_flagged is False
        assert res.action == "allow"
        assert res.account_count == i

    # 5th account from same IP must be flagged!
    res_5 = detector.record_and_evaluate(
        user_id="user_5",
        email="user_5@example.com",
        ip_address=ip,
    )
    assert res_5.is_flagged is True
    assert res_5.action in ("flag", "block")
    assert res_5.account_count == 5
    assert "Multi-account abuse detected" in res_5.reason


def test_device_fingerprint_flagging():
    detector = MultiAccountDetector(device_threshold=3)
    dev_fp = "fp_canvas_webgl_hash_98765"

    detector.record_and_evaluate("user_a", "a@test.com", "1.1.1.1", device_fingerprint=dev_fp)
    detector.record_and_evaluate("user_b", "b@test.com", "1.1.1.2", device_fingerprint=dev_fp)

    res_3 = detector.record_and_evaluate("user_c", "c@test.com", "1.1.1.3", device_fingerprint=dev_fp)
    assert res_3.is_flagged is True


def test_quota_gaming_disposable_email():
    detector = QuotaGamingDetector()

    # Normal email
    clean_res = detector.evaluate_account("user_norm", "alice@company.org")
    assert clean_res.is_gaming is False
    assert clean_res.is_disposable_email is False

    # Disposable burner email
    burner_res = detector.evaluate_account("user_burner", "spammer@mailinator.com")
    assert burner_res.is_gaming is True
    assert burner_res.is_disposable_email is True
    assert burner_res.action in ("restrict", "block")


def test_quota_gaming_token_exhaustion():
    detector = QuotaGamingDetector()
    res = detector.evaluate_account(
        user_id="user_exhaust",
        email="exhaust@gmail.com",
        free_tier_tokens_granted=100000,
        tokens_consumed=105000,
    )
    assert res.is_gaming is True
    assert any("exhausted" in r.lower() for r in res.reasons)


def test_one_thousand_rpm_script_blocked():
    """Acceptance Test: 1000 req/min script is blocked (Feature 10.50)."""
    detector = AutomatedMisuseDetector(block_threshold_rpm=1000)
    attacker_ip = "203.0.113.88"
    base_time = 1700000000.0

    # Simulate 999 requests
    for i in range(999):
        detector.evaluate_request(
            identifier=attacker_ip,
            now=base_time + (i * 0.05),
        )

    # 1000th request within the 60s window must be blocked!
    res_1000 = detector.evaluate_request(
        identifier=attacker_ip,
        now=base_time + 50.0,
    )
    assert res_1000.is_blocked is True
    assert res_1000.action == "block"
    assert res_1000.current_rpm >= 1000
    assert "Script blocked" in res_1000.reason


def test_bot_user_agent_detection():
    detector = AutomatedMisuseDetector()
    assert detector.is_bot_user_agent("curl/7.88.1") is True
    assert detector.is_bot_user_agent("python-requests/2.31.0") is True
    assert detector.is_bot_user_agent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/119.0.0.0") is True
    assert detector.is_bot_user_agent("") is True

    # Real browser user agent
    assert detector.is_bot_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36") is False


def test_account_manager_wiring_with_abuse_detector():
    account_mgr = AccountLifecycleManager()
    ip = "192.0.2.100"

    # Register 4 accounts cleanly
    for i in range(1, 5):
        account_mgr.create_account(
            user_id=f"acct_{i}",
            email=f"acct_{i}@test.com",
            ip_address=ip,
        )

    # 5th account from same IP is recorded in multi-account detector
    assessment = default_multi_account_detector.record_and_evaluate(
        user_id="acct_5",
        email="acct_5@test.com",
        ip_address=ip,
    )
    assert assessment.is_flagged is True
