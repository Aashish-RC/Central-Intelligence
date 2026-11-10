"""
Tests for Audit Log Cryptographic Tamper-Proofing & Chaining (Feature 10.36).
"""

import json
import pytest
from datetime import datetime, timezone

from control.safety.audit.ledger import IntegrityReport, UnifiedAuditLedger
from control.safety.audit.models import AuditSeverity, UnifiedAuditEntry, UserRole


def test_intact_audit_chain_verifies_cleanly():
    ledger = UnifiedAuditLedger(db_path=":memory:")

    # Append 5 audit entries
    for i in range(5):
        entry = UnifiedAuditEntry(
            id=f"entry_{i}",
            tenant_id="tenant_alpha",
            module="auth",
            action=f"login_step_{i}",
            resource=f"resource_{i}",
            role=UserRole.ADMIN,
            details={"step": i},
        )
        ledger.log(entry)

    assert ledger.verify_integrity() is True
    assert ledger.verify_chain() is True

    tampered, msg = ledger.detect_tampering()
    assert tampered is False
    assert msg is None

    report = ledger.verify_integrity_detailed()
    assert report.is_valid is True
    assert report.total_entries == 5
    assert report.merkle_root is not None
    assert len(report.merkle_root) == 64


def test_tampering_entry_action_invalidates_chain():
    """
    Acceptance criterion: Modifying any audit entry invalidates the chain; tampering detected.
    """
    ledger = UnifiedAuditLedger(db_path=":memory:")

    # Create 3 audit records
    for i in range(3):
        entry = UnifiedAuditEntry(
            id=f"rec_{i}",
            tenant_id="tenant_omega",
            module="vault",
            action="secret_access",
            resource=f"key_{i}",
            role=UserRole.SYSTEM,
            details={"key_index": i},
        )
        ledger.log(entry)

    assert ledger.verify_integrity() is True

    # Malicious direct mutation of entry 1 in the database
    conn = ledger._get_connection()
    conn.execute("UPDATE unified_audit_log SET action = 'unauthorized_export' WHERE id = 'rec_1'")
    conn.commit()

    # Verify tampering is immediately detected
    assert ledger.verify_integrity() is False
    assert ledger.verify_chain() is False

    is_tampered, message = ledger.detect_tampering()
    assert is_tampered is True
    assert "Payload tampered at entry rec_1" in message

    report = ledger.verify_integrity_detailed()
    assert report.is_valid is False
    assert report.tampered_entry_id == "rec_1"
    assert report.violation_type == "modified_entry_payload"


def test_tampering_details_json_invalidates_chain():
    ledger = UnifiedAuditLedger(db_path=":memory:")

    entry = UnifiedAuditEntry(
        id="tamper_json_01",
        tenant_id="tenant_x",
        module="billing",
        action="charge_card",
        resource="card_visa",
        details={"amount": 100},
    )
    ledger.log(entry)

    # Maliciously alter details_json directly in SQLite
    conn = ledger._get_connection()
    conn.execute("UPDATE unified_audit_log SET details_json = '{\"amount\": 9999}' WHERE id = 'tamper_json_01'")
    conn.commit()

    assert ledger.verify_integrity() is False
    report = ledger.verify_integrity_detailed()
    assert report.is_valid is False
    assert report.tampered_entry_id == "tamper_json_01"


def test_tampering_prev_hash_breaks_chain():
    ledger = UnifiedAuditLedger(db_path=":memory:")

    for i in range(3):
        entry = UnifiedAuditEntry(
            id=f"chain_rec_{i}",
            tenant_id="tenant_chain",
            module="compliance",
            action=f"verify_{i}",
            resource="policy",
        )
        ledger.log(entry)

    # Maliciously break the prev_hash link on entry 2
    conn = ledger._get_connection()
    conn.execute("UPDATE unified_audit_log SET prev_hash = 'tampered_bogus_hash' WHERE id = 'chain_rec_2'")
    conn.commit()

    assert ledger.verify_integrity() is False
    report = ledger.verify_integrity_detailed()
    assert report.is_valid is False
    assert report.tampered_entry_id == "chain_rec_2"
    assert report.violation_type == "broken_prev_hash"


def test_merkle_root_computation():
    ledger = UnifiedAuditLedger(db_path=":memory:")
    root_empty = ledger.get_merkle_root()
    assert len(root_empty) == 64

    entry = UnifiedAuditEntry(
        id="m_01",
        tenant_id="tenant_m",
        module="data",
        action="read",
        resource="blob",
    )
    ledger.log(entry)
    root_one = ledger.get_merkle_root()
    assert root_one != root_empty
    assert len(root_one) == 64

