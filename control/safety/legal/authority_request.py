"""
Lawful Authority Request Handler (Feature 10.47)
Processes government subpoenas, court orders, search warrants, and regulatory preservation notices.
Creates immutable, tamper-evident cryptographic audit records in the Unified Audit Ledger
and automatically initiates a Legal Hold to prevent spoliation of evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.audit.models import AuditSeverity, UnifiedAuditEntry, UserRole
from control.safety.legal.legal_hold import LegalHoldManager, LegalHoldRecord, default_legal_hold_manager


class RequestType(str, Enum):
    SUBPOENA = "subpoena"
    COURT_ORDER = "court_order"
    SEARCH_WARRANT = "search_warrant"
    REGULATORY_INQUIRY = "regulatory_inquiry"
    NATIONAL_SECURITY_LETTER = "nsl"


@dataclass
class AuthorityRequestRecord:
    request_id: str
    request_type: RequestType
    issuing_authority: str
    case_number: str
    target_user_id: str
    target_tenant_id: str = "default"
    status: str = "received"  # received, under_legal_review, fulfilled, challenged
    served_at: float = field(default_factory=time.time)
    fulfilled_at: Optional[float] = None
    audit_hash: str = ""
    associated_hold_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_audit_hash(self) -> str:
        payload = {
            "request_id": self.request_id,
            "request_type": self.request_type.value,
            "issuing_authority": self.issuing_authority,
            "case_number": self.case_number,
            "target_user_id": self.target_user_id,
            "target_tenant_id": self.target_tenant_id,
            "served_at": self.served_at,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuthorityRequestHandler:
    """
    Handles subpoenas, court orders, and lawful authority requests with full cryptographic audit.
    """

    def __init__(
        self,
        audit_ledger: Optional[UnifiedAuditLedger] = None,
        legal_hold_manager: Optional[LegalHoldManager] = None,
    ):
        self.ledger = audit_ledger or UnifiedAuditLedger(db_path=":memory:")
        self.hold_manager = legal_hold_manager or default_legal_hold_manager
        self._requests: Dict[str, AuthorityRequestRecord] = {}

    def record_request(
        self,
        request_type: RequestType | str,
        issuing_authority: str,
        case_number: str,
        target_user_id: str,
        target_tenant_id: str = "default",
        auto_place_legal_hold: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[AuthorityRequestRecord, Optional[LegalHoldRecord]]:
        """
        Ingests a lawful authority order, registers cryptographic audit record,
        and optionally places a preservation hold to prevent data destruction.
        """
        r_type = RequestType(request_type) if isinstance(request_type, str) else request_type
        req_id = f"auth_{uuid4().hex[:12]}"

        record = AuthorityRequestRecord(
            request_id=req_id,
            request_type=r_type,
            issuing_authority=issuing_authority,
            case_number=case_number,
            target_user_id=target_user_id,
            target_tenant_id=target_tenant_id,
            metadata=metadata or {},
        )
        record.audit_hash = record.calculate_audit_hash()

        # 1. Automatic Legal Hold Placement (Feature 10.46)
        hold_record: Optional[LegalHoldRecord] = None
        if auto_place_legal_hold:
            hold_record = self.hold_manager.place_hold(
                matter_name=f"{r_type.value.upper()}: {case_number}",
                issued_by=issuing_authority,
                tenant_id=target_tenant_id,
                user_id=target_user_id,
                metadata={"request_id": req_id, "case_number": case_number},
            )
            record.associated_hold_id = hold_record.hold_id

        self._requests[req_id] = record

        # 2. Immutable Cryptographic Audit Log (Feature 10.47)
        audit_entry = UnifiedAuditEntry(
            module="legal",
            action="lawful_authority_request_received",
            resource=f"case:{case_number}",
            role=UserRole.ADMIN.value,
            tenant_id=target_tenant_id,
            user_id=target_user_id,
            severity=AuditSeverity.WARNING,
            status="received",
            details={
                "request_id": req_id,
                "request_type": r_type.value,
                "issuing_authority": issuing_authority,
                "case_number": case_number,
                "audit_hash": record.audit_hash,
                "hold_id": hold_record.hold_id if hold_record else None,
            },
        )
        self.ledger.log(audit_entry)

        return record, hold_record

    def fulfill_request(
        self,
        request_id: str,
        fulfillment_notes: str = "Disclosed in accordance with lawful subpoena",
    ) -> AuthorityRequestRecord:
        """Marks request fulfilled and records immutable audit completion event."""
        if request_id not in self._requests:
            raise KeyError(f"Authority request '{request_id}' not found")

        record = self._requests[request_id]
        record.status = "fulfilled"
        record.fulfilled_at = time.time()

        audit_entry = UnifiedAuditEntry(
            module="legal",
            action="lawful_authority_request_fulfilled",
            resource=f"case:{record.case_number}",
            role=UserRole.ADMIN.value,
            tenant_id=record.target_tenant_id,
            user_id=record.target_user_id,
            severity=AuditSeverity.INFO,
            status="fulfilled",
            details={
                "request_id": request_id,
                "notes": fulfillment_notes,
            },
        )
        self.ledger.log(audit_entry)
        return record

    def get_request(self, request_id: str) -> AuthorityRequestRecord:
        if request_id not in self._requests:
            raise KeyError(f"Authority request '{request_id}' not found")
        return self._requests[request_id]

    def export_audit_trail(self, request_id: str) -> Dict[str, Any]:
        record = self.get_request(request_id)
        entries = self.ledger.query(tenant_id=record.target_tenant_id, module="legal")
        return {
            "request": {
                "request_id": record.request_id,
                "type": record.request_type.value,
                "authority": record.issuing_authority,
                "case": record.case_number,
                "status": record.status,
                "audit_hash": record.audit_hash,
            },
            "chain_valid": self.ledger.verify_chain(),
            "audit_events": [
                {
                    "action": e.action,
                    "timestamp": e.timestamp,
                    "status": e.status,
                    "details": e.details,
                }
                for e in entries
            ],
        }


# Global default handler instance
default_authority_handler = AuthorityRequestHandler()
