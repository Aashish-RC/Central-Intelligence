"""
Tests for Billing Audit & Dispute Resolution Workflow (Feature 13.17).
"""

from unittest.mock import MagicMock
import pytest

from control.billing.audit.billing_audit import (
    BillingAuditManager,
    DisputeStatus,
)
from control.safety.audit.ledger import UnifiedAuditLedger


def test_can_audit_any_charge_user_can_dispute_and_get_resolution():
    """
    Acceptance criterion: Can audit any charge; user can dispute and get resolution.
    """
    ledger = UnifiedAuditLedger(db_path=":memory:")
    mock_hyperswitch = MagicMock()
    manager = BillingAuditManager(audit_ledger=ledger, hyperswitch_adapter=mock_hyperswitch)

    charge_id = "chg_audit_100_usd"
    customer_id = "cust_disputing_user"

    # 1. Record an auditable charge ($50.00)
    record = manager.record_charge(
        charge_id=charge_id,
        customer_id=customer_id,
        amount_cents=5000,
        description="High volume batch job",
        payment_gateway="stripe",
        tenant_id="tenant_finance",
    )

    # Verify cryptographic anchoring in Layer 10 ledger
    assert record.ledger_entry_hash is not None
    assert len(record.ledger_entry_hash) == 64

    # Audit the charge
    audit_data = manager.audit_charge(charge_id)
    assert audit_data["charge_id"] == charge_id
    assert audit_data["amount_usd"] == 50.0
    assert audit_data["status"] == "settled"
    assert audit_data["is_cryptographically_anchored"] is True

    # 2. User disputes the charge
    dispute = manager.open_dispute(
        charge_id=charge_id,
        customer_id=customer_id,
        reason="Model failed to produce expected batch output",
        evidence="Logs indicate worker node crash midway through job",
    )

    assert dispute.status == DisputeStatus.OPEN
    assert dispute.charge_id == charge_id

    # Check charge status is now 'disputed'
    assert manager.audit_charge(charge_id)["status"] == "disputed"

    # 3. Dispute Resolution: Refund approved
    resolved_dispute = manager.resolve_dispute(
        dispute_id=dispute.dispute_id,
        resolution="refund",
        notes="Worker node outage confirmed from telemetry. Full refund approved.",
        resolved_by="compliance_officer_sara",
    )

    assert resolved_dispute.status == DisputeStatus.RESOLVED_REFUNDED
    assert resolved_dispute.resolved_by == "compliance_officer_sara"

    # Verify charge status is now 'resolved_refunded'
    updated_audit = manager.audit_charge(charge_id)
    assert updated_audit["status"] == "resolved_refunded"

    # Verify Hyperswitch refund was invoked
    mock_hyperswitch.refund_payment.assert_called_once_with(
        payment_id=charge_id,
        amount_cents=5000,
        reason=f"Dispute {dispute.dispute_id} resolved in customer favor",
    )


def test_dispute_resolution_upheld():
    ledger = UnifiedAuditLedger(db_path=":memory:")
    manager = BillingAuditManager(audit_ledger=ledger)

    charge_id = "chg_legit_20"
    manager.record_charge(charge_id=charge_id, customer_id="cust_legit", amount_cents=2000)

    dispute = manager.open_dispute(charge_id, "cust_legit", reason="Unclear invoice line item")
    resolved = manager.resolve_dispute(dispute.dispute_id, resolution="uphold", notes="Valid tokens delivered")

    assert resolved.status == DisputeStatus.RESOLVED_UPHELD
    assert manager.audit_charge(charge_id)["status"] == "resolved_upheld"


def test_audit_non_existent_charge_raises_key_error():
    manager = BillingAuditManager()
    with pytest.raises(KeyError):
        manager.audit_charge("chg_missing")

