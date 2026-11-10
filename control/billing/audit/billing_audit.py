"""
Billing Audit Trails & Dispute Resolution Workflow (Layer 13: Feature 13.17).

Features:
- 13.17: Comprehensive billing auditability and dispute management:
  - Cryptographic audit trail for every monetary and credit transaction (wired into Layer 10 Unified Merkle Ledger).
  - Dispute resolution lifecycle: open dispute, review evidence, execute resolution (refund vs uphold).
  - Automated Hyperswitch settlement on dispute concession/refund.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("control.billing.audit")


class DisputeStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED_REFUNDED = "resolved_refunded"
    RESOLVED_UPHELD = "resolved_upheld"


@dataclass
class BillingDispute:
    """Formal dispute raised against a billing transaction."""
    dispute_id: str
    charge_id: str
    customer_id: str
    reason: str
    evidence: str = ""
    status: DisputeStatus = DisputeStatus.OPEN
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    opened_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None


@dataclass
class ChargeAuditRecord:
    """Auditable billing charge with cryptographic ledger hash link."""
    charge_id: str
    customer_id: str
    amount_cents: int
    currency: str = "USD"
    description: str = "Platform invocation charge"
    payment_gateway: str = "stripe"
    invoice_id: Optional[str] = None
    tenant_id: str = "default"
    ledger_entry_hash: Optional[str] = None
    status: str = "settled"  # "settled", "disputed", "resolved_refunded", "resolved_upheld"
    dispute: Optional[BillingDispute] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BillingAuditManager:
    """
    Manages immutable billing audit records and customer dispute workflows (Feature 13.17).
    """

    def __init__(
        self,
        audit_ledger: Optional[Any] = None,
        hyperswitch_adapter: Optional[Any] = None,
    ) -> None:
        self._ledger = audit_ledger
        self._hyperswitch = hyperswitch_adapter
        self._charges: Dict[str, ChargeAuditRecord] = {}  # charge_id -> record
        self._disputes: Dict[str, BillingDispute] = {}    # dispute_id -> dispute

    def _get_ledger(self) -> Any:
        if self._ledger is None:
            try:
                from control.safety.audit.ledger import default_audit_ledger
                self._ledger = default_audit_ledger
            except ImportError:
                pass
        return self._ledger

    def _get_hyperswitch(self) -> Any:
        if self._hyperswitch is None:
            try:
                from control.billing.payments.hyperswitch_adapter import default_hyperswitch_adapter
                self._hyperswitch = default_hyperswitch_adapter
            except ImportError:
                pass
        return self._hyperswitch

    def record_charge(
        self,
        charge_id: str,
        customer_id: str,
        amount_cents: int,
        currency: str = "USD",
        description: str = "Token usage charge",
        payment_gateway: str = "stripe",
        invoice_id: Optional[str] = None,
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChargeAuditRecord:
        """
        Records a transaction and cryptographically logs it into Layer 10 Unified Audit Ledger.
        """
        rec = ChargeAuditRecord(
            charge_id=charge_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            payment_gateway=payment_gateway,
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            metadata=metadata or {},
        )

        # Wire with Layer 10 Merkle Ledger (Feature 10.36)
        ledger = self._get_ledger()
        if ledger and hasattr(ledger, "log"):
            try:
                from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity, UserRole
                entry = UnifiedAuditEntry(
                    id=f"audit_chg_{charge_id}",
                    tenant_id=tenant_id,
                    user_id=customer_id,
                    role=UserRole.SYSTEM,
                    module="billing",
                    action="charge_captured",
                    resource=f"charge:{charge_id}",
                    status="success",
                    severity=AuditSeverity.INFO,
                    details={
                        "amount_cents": amount_cents,
                        "currency": currency,
                        "gateway": payment_gateway,
                        "invoice_id": invoice_id,
                    },
                )
                rec.ledger_entry_hash = ledger.log(entry)
            except Exception as e:
                logger.debug("Failed logging charge to L10 Merkle ledger: %s", e)

        self._charges[charge_id] = rec
        logger.info("Recorded auditable charge %s ($%.2f) for customer %s", charge_id, amount_cents / 100.0, customer_id)
        return rec

    def audit_charge(self, charge_id: str) -> Dict[str, Any]:
        """
        Audits any charge, returning its verified status and ledger trail (Feature 13.17).
        """
        if charge_id not in self._charges:
            raise KeyError(f"Charge '{charge_id}' not found in audit ledger.")

        rec = self._charges[charge_id]
        return {
            "charge_id": rec.charge_id,
            "customer_id": rec.customer_id,
            "amount_cents": rec.amount_cents,
            "amount_usd": round(rec.amount_cents / 100.0, 2),
            "currency": rec.currency,
            "description": rec.description,
            "payment_gateway": rec.payment_gateway,
            "invoice_id": rec.invoice_id,
            "tenant_id": rec.tenant_id,
            "status": rec.status,
            "ledger_entry_hash": rec.ledger_entry_hash,
            "is_cryptographically_anchored": rec.ledger_entry_hash is not None,
            "dispute": rec.dispute.__dict__ if rec.dispute else None,
            "timestamp": rec.timestamp,
        }

    def open_dispute(
        self,
        charge_id: str,
        customer_id: str,
        reason: str,
        evidence: str = "",
    ) -> BillingDispute:
        """
        Initiates a formal billing dispute on a transaction.
        """
        if charge_id not in self._charges:
            raise KeyError(f"Cannot dispute non-existent charge '{charge_id}'")

        charge = self._charges[charge_id]
        dispute_id = f"disp_{uuid4().hex[:10]}"
        dispute = BillingDispute(
            dispute_id=dispute_id,
            charge_id=charge_id,
            customer_id=customer_id,
            reason=reason,
            evidence=evidence,
            status=DisputeStatus.OPEN,
        )

        charge.status = "disputed"
        charge.dispute = dispute
        self._disputes[dispute_id] = dispute

        # Log dispute event to L10 Audit Ledger
        ledger = self._get_ledger()
        if ledger and hasattr(ledger, "log"):
            try:
                from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity, UserRole
                entry = UnifiedAuditEntry(
                    id=f"audit_{dispute_id}",
                    tenant_id=charge.tenant_id,
                    user_id=customer_id,
                    role=UserRole.MEMBER,
                    module="billing",
                    action="dispute_opened",
                    resource=f"charge:{charge_id}",
                    status="open",
                    severity=AuditSeverity.WARNING,
                    details={"dispute_id": dispute_id, "reason": reason},
                )
                ledger.log(entry)
            except Exception:
                pass

        logger.warning("Dispute %s opened on charge %s by customer %s", dispute_id, charge_id, customer_id)
        return dispute

    def resolve_dispute(
        self,
        dispute_id: str,
        resolution: str,  # "refund" or "uphold"
        notes: str,
        resolved_by: str = "compliance_officer",
    ) -> BillingDispute:
        """
        Executes formal dispute resolution workflow (Feature 13.17):
        - resolution="refund": triggers automatic refund in Hyperswitch and marks charge resolved_refunded.
        - resolution="uphold": marks charge resolved_upheld.
        """
        if dispute_id not in self._disputes:
            raise KeyError(f"Dispute '{dispute_id}' not found.")

        dispute = self._disputes[dispute_id]
        charge = self._charges[dispute.charge_id]

        clean_res = resolution.strip().lower()
        now = time.time()

        if clean_res in ("refund", "resolved_refunded"):
            dispute.status = DisputeStatus.RESOLVED_REFUNDED
            charge.status = "resolved_refunded"

            # Trigger automated Hyperswitch refund if adapter available
            hs = self._get_hyperswitch()
            if hs and hasattr(hs, "refund_payment"):
                try:
                    hs.refund_payment(
                        payment_id=charge.charge_id,
                        amount_cents=charge.amount_cents,
                        reason=f"Dispute {dispute_id} resolved in customer favor",
                    )
                except Exception:
                    pass

        elif clean_res in ("uphold", "resolved_upheld"):
            dispute.status = DisputeStatus.RESOLVED_UPHELD
            charge.status = "resolved_upheld"
        else:
            raise ValueError(f"Invalid dispute resolution '{resolution}'. Expected 'refund' or 'uphold'.")

        dispute.resolution_notes = notes
        dispute.resolved_by = resolved_by
        dispute.resolved_at = now

        # Record resolution in L10 Audit Ledger
        ledger = self._get_ledger()
        if ledger and hasattr(ledger, "log"):
            try:
                from control.safety.audit.models import UnifiedAuditEntry, AuditSeverity, UserRole
                entry = UnifiedAuditEntry(
                    id=f"audit_res_{dispute_id}",
                    tenant_id=charge.tenant_id,
                    user_id=resolved_by,
                    role=UserRole.ADMIN,
                    module="billing",
                    action=f"dispute_{dispute.status.value}",
                    resource=f"charge:{charge.charge_id}",
                    status="resolved",
                    severity=AuditSeverity.INFO,
                    details={"dispute_id": dispute_id, "resolution": clean_res, "notes": notes},
                )
                ledger.log(entry)
            except Exception:
                pass

        logger.info("Dispute %s resolved (%s) by %s", dispute_id, dispute.status.value, resolved_by)
        return dispute


# Global default singleton
default_billing_audit_manager = BillingAuditManager()

