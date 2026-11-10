"""
Tests for Billing Quota Gaming & Free-Tier Abuse Detection (Feature 13.18).
"""

import pytest

from control.billing.abuse.quota_gaming import (
    BillingQuotaGamingDetector,
    QuotaGamingResult,
)


def test_user_hitting_limit_then_creating_new_account_is_flagged():
    """
    Acceptance criterion: User hitting limit then creating new account is flagged.
    """
    detector = BillingQuotaGamingDetector()

    shared_ip = "198.51.100.42"
    shared_device = "fp_chrome_win_a8f9"

    # User 1 registers and exhausts free-tier quota
    user1_id = "user_original_01"
    detector.record_quota_exhaustion(
        user_id=user1_id,
        email="gamer.alice@gmail.com",
        ip_address=shared_ip,
        device_fingerprint=shared_device,
    )

    # User 2 immediately registers from the same IP / device fingerprint
    user2_id = "user_churn_02"
    assessment: QuotaGamingResult = detector.evaluate_new_account(
        user_id=user2_id,
        email="gamer.alice.alt@yahoo.com",
        ip_address=shared_ip,
        device_fingerprint=shared_device,
    )

    # Must be detected and flagged
    assert assessment.is_gaming is True
    assert assessment.action in ("flag", "block")
    assert user1_id in assessment.prior_exhausted_accounts
    assert any("exhausted free-tier" in r for r in assessment.reasons)


def test_plus_email_alias_free_tier_gaming():
    detector = BillingQuotaGamingDetector()

    # User exhausts quota with primary email
    detector.record_quota_exhaustion(
        user_id="user_bob_primary",
        email="bob.builder@gmail.com",
    )

    # User tries creating new account with bob.builder+1@gmail.com
    assessment = detector.evaluate_new_account(
        user_id="user_bob_alt1",
        email="bob.builder+1@gmail.com",
    )

    assert assessment.is_gaming is True
    assert assessment.action in ("flag", "block")
    assert "user_bob_primary" in assessment.prior_exhausted_accounts
    assert any("canonical base" in r for r in assessment.reasons)


def test_clean_user_registration_allowed():
    detector = BillingQuotaGamingDetector()

    assessment = detector.evaluate_new_account(
        user_id="user_legit_new",
        email="brand_new_user@company.org",
        ip_address="203.0.113.88",
    )

    assert assessment.is_gaming is False
    assert assessment.action == "allow"
    assert assessment.risk_score == 0.0
    assert len(assessment.reasons) == 0


def test_bridge_to_l10_safety_quota_detector():
    from control.safety.abuse.quota_gaming_detector import QuotaGamingDetector
    safety_detector = QuotaGamingDetector()
    billing_detector = BillingQuotaGamingDetector(safety_quota_detector=safety_detector)

    # Disposable burner email
    res = billing_detector.evaluate_new_account(
        user_id="burner_user",
        email="temp_user@mailinator.com",
    )

    assert res.is_gaming is True
    assert any("disposable email domain" in r for r in res.reasons)

