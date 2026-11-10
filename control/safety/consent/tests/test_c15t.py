"""
Unit & Integration Tests for c15t Consent Management Adapter (10.29, 10.35)
Verifies explicit opt-in, Privacy Mode, zero-retention logging, and audit receipts.
"""

import pytest
from control.safety.consent.c15t_adapter import (
    C15tConsentAdapter,
    ConsentPurpose,
)
from control.observability.log_routing.tier_router import (
    LogEntry,
    TieredLogRouter,
)
from control.safety.pii import DataClass, FourTierPIIScrubber


@pytest.fixture
def consent_adapter():
    return C15tConsentAdapter(default_opt_in=False)


def test_default_consent_opt_in_denied(consent_adapter):
    user_id = "user_anon_1"
    assert consent_adapter.has_consent(user_id, ConsentPurpose.TELEMETRY) is False
    assert consent_adapter.has_consent(user_id, ConsentPurpose.MODEL_TRAINING) is False
    assert consent_adapter.has_consent(user_id, ConsentPurpose.DIAGNOSTICS) is False
    assert consent_adapter.is_privacy_mode(user_id) is False


def test_grant_and_revoke_consent(consent_adapter):
    user_id = "user_alpha"
    # Explicit opt-in
    record = consent_adapter.grant_consent(
        user_id,
        purposes=[ConsentPurpose.TELEMETRY, ConsentPurpose.DIAGNOSTICS],
    )
    assert consent_adapter.has_consent(user_id, ConsentPurpose.TELEMETRY) is True
    assert consent_adapter.has_consent(user_id, ConsentPurpose.DIAGNOSTICS) is True
    assert consent_adapter.has_consent(user_id, ConsentPurpose.MODEL_TRAINING) is False
    assert record.receipt_hash is not None

    # Revoke telemetry
    consent_adapter.revoke_consent(user_id, purposes=[ConsentPurpose.TELEMETRY])
    assert consent_adapter.has_consent(user_id, ConsentPurpose.TELEMETRY) is False
    assert consent_adapter.has_consent(user_id, ConsentPurpose.DIAGNOSTICS) is True


def test_privacy_mode_enforcement(consent_adapter):
    user_id = "user_stealth"
    # Even if user previously granted consent
    consent_adapter.grant_consent(user_id, purposes=[ConsentPurpose.TELEMETRY, ConsentPurpose.MODEL_TRAINING])
    assert consent_adapter.has_consent(user_id, ConsentPurpose.TELEMETRY) is True

    # User turns on Privacy Mode (Feature 10.35)
    rec = consent_adapter.set_privacy_mode(user_id, enabled=True)
    assert rec.privacy_mode is True
    assert consent_adapter.is_privacy_mode(user_id) is True

    # Immediate revocation of all telemetry and training
    assert consent_adapter.has_consent(user_id, ConsentPurpose.TELEMETRY) is False
    assert consent_adapter.has_consent(user_id, ConsentPurpose.MODEL_TRAINING) is False
    assert consent_adapter.has_consent(user_id, ConsentPurpose.DIAGNOSTICS) is False


def test_privacy_mode_user_has_zero_data_in_logs():
    """Acceptance Test: Privacy-mode user has zero data in logs."""
    consent = C15tConsentAdapter()
    router = TieredLogRouter(consent_adapter=consent)

    privacy_user = "user_zdr_stealth"
    consent.set_privacy_mode(privacy_user, enabled=True)

    entry = LogEntry(
        content="Diagnostic state: User accessed secure vault key sk_test_12345",
        level="INFO",
        user_id=privacy_user,
        tenant_id="tenant_confidential",
    )

    # Route diagnostic entry without explicit caller flag; consent adapter should enforce privacy mode
    scrubbed = router.route(entry, data_class=DataClass.DIAGNOSTIC)

    # Tier 4 ZDR must be enforced
    assert scrubbed.tier == 4
    assert scrubbed.stored is False
    assert scrubbed.retained_days == 0
    assert "retained_days" in router.get_routed_history()[-1]
    assert router.get_routed_history()[-1]["stored"] is False


def test_scrubber_privacy_mode_upgrade():
    consent = C15tConsentAdapter()
    scrubber = FourTierPIIScrubber(consent_adapter=consent)

    user_id = "user_privacy_direct"
    consent.set_privacy_mode(user_id, enabled=True)

    result = scrubber.scrub(
        data="Session info with email test@example.com",
        data_class=DataClass.DIAGNOSTIC,
        user_id=user_id,
    )

    assert result.tier == 4
    assert result.stored is False
    assert result.retained_days == 0


def test_compliance_receipt_export(consent_adapter):
    user_id = "user_audit_gdpr"
    consent_adapter.grant_consent(user_id, [ConsentPurpose.TELEMETRY])
    receipt = consent_adapter.export_audit_receipt(user_id)

    assert receipt["user_id"] == user_id
    assert receipt["purposes"][ConsentPurpose.TELEMETRY.value] is True
    assert len(receipt["receipt_hash"]) == 64

