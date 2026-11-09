"""Unit tests for Context Audit Log (Task 9.4, Feature 9.13)."""

import sqlite3
import pytest
from unittest.mock import MagicMock
from control.context.audit.context_audit import ContextAuditLog, ContextAuditRecord


@pytest.fixture
def audit_log(tmp_path):
    db_file = str(tmp_path / "context_audit_test.db")
    mock_ledger = MagicMock()
    return ContextAuditLog(db_path=db_file, safety_ledger=mock_ledger)


def test_context_audit_record_and_reconstruction_acceptance(audit_log):
    """Task 9.4 Acceptance: Can reconstruct exactly what context was sent to the model for any past response."""
    raw_prompt_payload = (
        "<system_instruction trust=\"system\" mutable=\"false\">\n"
        "You are an enterprise AI assistant.\n"
        "</system_instruction>\n"
        "<untrusted_content source=\"user\" trust=\"low\">\n"
        "Summarize quarterly financial disclosures.\n"
        "</untrusted_content>"
    )
    resp_id = "resp_20261110_abc123"

    # Record context
    record = audit_log.record(
        response_id=resp_id,
        raw_prompt=raw_prompt_payload,
        user_id="alice",
        session_id="sess_finance_01",
        tenant_id="tenant_acme",
        token_count=48,
        sources_included=["system", "user"],
        injections_flagged=0,
        metadata={"model": "gpt-4-turbo"},
    )

    assert record.response_id == resp_id
    assert len(record.sha256_hash) == 64

    # 1. Retrieval
    retrieved = audit_log.get_record(resp_id)
    assert retrieved is not None
    assert retrieved.sha256_hash == record.sha256_hash
    assert retrieved.user_id == "alice"
    assert retrieved.token_count == 48

    # 2. Byte-for-byte reconstruction acceptance
    reconstructed_text = audit_log.reconstruct(resp_id)
    assert reconstructed_text == raw_prompt_payload

    # 3. Cryptographic integrity check
    assert audit_log.verify_integrity(resp_id) is True

    # 4. Verified bridge to L10 safety ledger
    audit_log.safety_ledger.record_action.assert_called_once()


def test_context_audit_tamper_detection(audit_log):
    """Feature 9.13: Verify tampering of underlying records is flagged."""
    resp_id = "resp_tamper_test"
    original_prompt = "Legitimate context payload."
    audit_log.record(
        response_id=resp_id,
        raw_prompt=original_prompt,
    )

    assert audit_log.verify_integrity(resp_id) is True

    # Tamper with the raw prompt directly in SQLite database
    with sqlite3.connect(audit_log.db_path) as conn:
        conn.execute(
            "UPDATE context_audit_records SET raw_prompt = ? WHERE response_id = ?",
            ("Maliciously altered prompt payload.", resp_id),
        )
        conn.commit()

    # Integrity verification must fail
    assert audit_log.verify_integrity(resp_id) is False
