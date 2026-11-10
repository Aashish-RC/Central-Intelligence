"""Test Suite for 4-Tier PII & Telemetry Scrubber Crown Jewel.
(Features 10.30 & 14.19)
"""

import time
import pytest
from control.safety.pii import (
    FourTierPIIScrubber,
    DataClass,
    RetentionPolicy,
    ScrubberConfig,
    PIIDetector,
    Redactor,
    luhn_checksum,
)
from control.safety.audit.ledger import UnifiedAuditLedger


@pytest.fixture
def scrubber():
    config = ScrubberConfig(
        default_retention=RetentionPolicy(
            telemetry_ttl=90,
            diagnostic_ttl=14,
            audit_ttl=365,
            zdr_ttl_seconds=1,  # Short TTL for test
        )
    )
    ledger = UnifiedAuditLedger(db_path=":memory:")
    return FourTierPIIScrubber(config=config, unified_ledger=ledger)


def test_1_credit_card_redacted_and_routed_tier_2(scrubber):
    """Test 1: Credit card number in prompt -> detected, redacted, routed to Tier 2."""
    # Valid Visa test number (passes Luhn)
    valid_cc = "4532-0150-1234-5674"
    prompt = f"Please charge my credit card {valid_cc} for my subscription renewal."

    scrubbed = scrubber.scrub(
        data=prompt,
        data_class=DataClass.DIAGNOSTIC,
        user_id="user_alice",
        session_id="sess_123",
    )

    assert scrubbed.tier == 2
    assert scrubbed.stored is True
    assert scrubbed.retained_days == 14
    assert valid_cc not in scrubbed.data
    assert "[REDACTED_CREDIT_CARD]" in scrubbed.data

    findings = scrubbed.findings
    assert len(findings) >= 1
    assert any(f.entity_type == "CREDIT_CARD" for f in findings)

    # Diagnostic store inspection
    records = scrubber.tier2.get_records(user_id="user_alice")
    assert len(records) == 1
    assert valid_cc not in records[0].redacted_content
    assert "[REDACTED_CREDIT_CARD]" in records[0].redacted_content


def test_2_telemetry_data_tier_1_no_pii_leaked(scrubber):
    """Test 2: Telemetry data (tokens, latency) -> Tier 1, user_id hashed, no PII leaked."""
    telemetry_payload = {
        "model": "gpt-4o",
        "prompt_tokens": 128,
        "completion_tokens": 42,
        "total_tokens": 170,
        "latency_ms": 234.5,
        "cost_usd": 0.0035,
        "user_email": "alice.smith@example.com",  # PII inside telemetry payload!
    }

    scrubbed = scrubber.scrub(
        data=telemetry_payload,
        data_class=DataClass.TELEMETRY,
        user_id="alice_user_999",
    )

    assert scrubbed.tier == 1
    assert scrubbed.stored is True
    assert scrubbed.retained_days == 90
    assert scrubbed.data["prompt_tokens"] == 128
    assert scrubbed.data["total_tokens"] == 170
    assert "alice.smith@example.com" not in str(scrubbed.data)
    assert "[REDACTED_EMAIL]" in scrubbed.data["user_email"]

    # Verify user_id is pseudonymized / hashed
    records = scrubber.tier1.get_records(user_id="alice_user_999")
    assert len(records) == 1
    assert records[0].user_hash != "alice_user_999"
    assert len(records[0].user_hash) == 16


def test_3_agent_action_tier_3_encrypted_audit(scrubber):
    """Test 3: Agent action (send email) -> Tier 3, encrypted, 1-year retention."""
    action_payload = {
        "action": "send_email",
        "to": "boss@enterprise.com",
        "subject": "Quarterly Financial Overview",
        "authorized_by": "user_alice",
        "timestamp": "2026-11-10T05:00:00Z",
    }

    scrubbed = scrubber.scrub(
        data=action_payload,
        data_class=DataClass.AUDIT,
        user_id="user_alice",
        metadata={"action": "send_email"},
    )

    assert scrubbed.tier == 3
    assert scrubbed.stored is True
    assert scrubbed.retained_days == 365
    assert "boss@enterprise.com" not in scrubbed.data  # Encrypted ciphertext!

    # Decrypt and verify payload fidelity in Tier 3 ledger
    records = scrubber.tier3.get_records(user_id="user_alice")
    assert len(records) == 1
    decrypted = scrubber.tier3.decrypt(records[0].encrypted_payload)
    assert decrypted["action"] == "send_email"
    assert decrypted["to"] == "boss@enterprise.com"


def test_4_zdr_mode_tier_4_purged_after_ttl(scrubber):
    """Test 4: ZDR mode -> Tier 4, in-memory only, purged after expiry."""
    confidential_prompt = "Top secret patent disclosure document."

    scrubbed = scrubber.scrub(
        data=confidential_prompt,
        data_class=DataClass.ZDR,
        user_id="user_alice",
    )

    assert scrubbed.tier == 4
    assert scrubbed.stored is False
    assert scrubbed.retained_days == 0
    assert scrubbed.data == confidential_prompt

    item_id = scrubbed.metadata["zdr_item_id"]
    # Retrieve before expiration
    held = scrubber.tier4.retrieve_and_purge(item_id)
    assert held == confidential_prompt

    # Atomic retrieval should leave RAM buffer empty
    assert scrubber.tier4.active_count() == 0

    # Test auto-expiry
    item_id_2 = scrubber.tier4.hold_in_memory("Another secret", "user_alice", ttl_seconds=1)
    assert scrubber.tier4.active_count() == 1
    time.sleep(1.1)
    assert scrubber.tier4.retrieve_and_purge(item_id_2) is None
    assert scrubber.tier4.active_count() == 0


def test_5_right_to_erasure_purges_all_tiers(scrubber):
    """Test 5: Right-to-erasure -> all 4 tiers purged for user."""
    user = "user_to_erase"

    # Seed data into all 4 tiers
    scrubber.scrub({"prompt_tokens": 50}, DataClass.TELEMETRY, user_id=user)
    scrubber.scrub("Diagnostic message", DataClass.DIAGNOSTIC, user_id=user)
    scrubber.scrub({"action": "exec_code"}, DataClass.AUDIT, user_id=user)
    scrubber.scrub("Secret memo", DataClass.ZDR, user_id=user)

    assert len(scrubber.tier1.get_records(user_id=user)) == 1
    assert len(scrubber.tier2.get_records(user_id=user)) == 1
    assert len(scrubber.tier3.get_records(user_id=user)) == 1
    assert scrubber.tier4.active_count() >= 1

    # Execute universal right-to-erasure
    report = scrubber.purge_all(user_id=user)

    assert report["total_purged"] >= 4
    assert len(scrubber.tier1.get_records(user_id=user)) == 0
    assert len(scrubber.tier2.get_records(user_id=user)) == 0
    assert len(scrubber.tier3.get_records(user_id=user)) == 0


def test_6_openai_sk_proj_api_key_detected_and_redacted(scrubber):
    """Test 6: sk-proj- and sk- API keys are detected by pattern and redacted."""
    raw = "My OpenAI key is sk-proj-a1B2c3D4e5F6g7H8i9J0kLMN and backup is sk-1234567890abcdef1234567890."
    scrubbed = scrubber.scrub(raw, DataClass.DIAGNOSTIC, user_id="dev_bob")

    assert "sk-proj-a1B2c3D4e5F6g7H8i9J0kLMN" not in scrubbed.data
    assert "sk-1234567890abcdef1234567890" not in scrubbed.data
    assert "[REDACTED_SECRET_KEY]" in scrubbed.data


def test_7_ssn_email_phone_all_detected_and_redacted(scrubber):
    """Test 7: SSN, email, phone are all detected and redacted."""
    text = (
        "Contact me at john.doe@workplace.org or +1 (555) 234-5678. "
        "My SSN for payroll is 123-45-6789."
    )
    scrubbed = scrubber.scrub(text, DataClass.DIAGNOSTIC, user_id="worker")

    assert "john.doe@workplace.org" not in scrubbed.data
    assert "123-45-6789" not in scrubbed.data
    assert "(555) 234-5678" not in scrubbed.data

    assert "[REDACTED_EMAIL]" in scrubbed.data
    assert "[REDACTED_SSN]" in scrubbed.data
    assert "[REDACTED_PHONE]" in scrubbed.data


def test_8_partial_masking_utility():
    """Test 8: Partial masking formats for credit cards, SSN, and email."""
    redactor = Redactor()
    text = "Card: 4532-0150-1234-5674, SSN: 123-45-6789, Email: testuser@company.com"
    masked = redactor.mask_partially(text)

    assert "****-****-****-5674" in masked
    assert "***-**-6789" in masked
    assert "t***@company.com" in masked
