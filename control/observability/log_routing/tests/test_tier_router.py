"""Test Suite for 4-Tier Structured Log Router (Features 14.19 & 10.30)."""

import pytest
from control.observability.log_routing import LogEntry, TieredLogRouter
from control.observability.signoz import SigNozAdapter
from control.safety.pii import DataClass, FourTierPIIScrubber


@pytest.fixture
def router():
    scrubber = FourTierPIIScrubber()
    signoz = SigNozAdapter()
    return TieredLogRouter(scrubber=scrubber, signoz=signoz)


def test_1_log_entry_pii_scrubbed_tier_2(router):
    """Test 1: Sensitive user PII (SSN, email) is sanitized before diagnostic storage."""
    entry = LogEntry(
        content="User alice.smith@corp.com updated SSN 123-45-6789 in profile.",
        level="INFO",
        user_id="alice",
    )

    scrubbed = router.route(entry, data_class=DataClass.DIAGNOSTIC)
    assert scrubbed.tier == 2
    assert scrubbed.stored is True
    assert "alice.smith@corp.com" not in scrubbed.data
    assert "123-45-6789" not in scrubbed.data
    assert "[REDACTED_EMAIL]" in scrubbed.data
    assert "[REDACTED_SSN]" in scrubbed.data


def test_2_telemetry_routes_to_tier_1_and_signoz(router):
    """Test 2: Operational telemetry routes to Tier 1 and emits SigNoz metric."""
    entry = LogEntry(
        content="Inference completed in 120ms with 450 tokens.",
        level="INFO",
        user_id="bob",
        tenant_id="tenant_1",
    )

    scrubbed = router.route(entry, data_class=DataClass.TELEMETRY)
    assert scrubbed.tier == 1
    assert scrubbed.stored is True
    assert scrubbed.retained_days == 90

    # Verify SigNoz received counter
    metrics = [m for m in router.signoz._metrics if m.name == "log.telemetry.events"]
    assert len(metrics) == 1
    assert metrics[0].labels["tenant_id"] == "tenant_1"


def test_3_action_audit_routes_to_tier_3_encrypted(router):
    """Test 3: Security action routes to Tier 3 with cryptographic encryption."""
    entry = LogEntry(
        content="Agent deleted database table 'test_archive' on tenant request.",
        level="WARN",
        user_id="agent_bot",
        tenant_id="tenant_x",
    )

    scrubbed = router.route(entry, data_class=DataClass.AUDIT)
    assert scrubbed.tier == 3
    assert scrubbed.stored is True
    assert scrubbed.retained_days == 365
    assert "test_archive" not in scrubbed.data  # Ciphertext


def test_4_privacy_mode_forces_zdr_tier_4(router):
    """Test 4: Privacy mode forces Tier 4 (ZDR), zero disk retention."""
    entry = LogEntry(
        content="Confidential health query asked by patient.",
        level="DEBUG",
        user_id="patient_123",
    )

    scrubbed = router.route(entry, data_class=DataClass.DIAGNOSTIC, privacy_mode=True)
    assert scrubbed.tier == 4
    assert scrubbed.stored is False
    assert scrubbed.retained_days == 0

    # Volatile item held in RAM
    zdr_id = scrubbed.metadata["zdr_item_id"]
    val = router.scrubber.tier4.retrieve_and_purge(zdr_id)
    assert val == entry.content


def test_5_openai_api_key_redacted_in_logs(router):
    """Test 5: Accidental secret token dump in logs is scrubbed."""
    entry = LogEntry(
        content="Provider request failed using key sk-proj-1234567890abcdef1234567890.",
        level="ERROR",
        user_id="developer",
    )

    scrubbed = router.route(entry, data_class=DataClass.DIAGNOSTIC)
    assert "sk-proj-1234567890abcdef1234567890" not in scrubbed.data
    assert "[REDACTED_SECRET_KEY]" in scrubbed.data
