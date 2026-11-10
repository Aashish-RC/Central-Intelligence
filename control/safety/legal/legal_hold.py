"""
Legal Hold Manager (Feature 10.46)
Places legal holds on user and tenant data in response to litigation, regulatory inquiries,
or ongoing compliance investigations.
Suspends and prevents automated or requested right-to-erasure and data purging.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from control.safety.privacy.erasure_propagator import LegalHoldActiveError


class LegalHoldStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass
class LegalHoldRecord:
    hold_id: str
    matter_name: str
    issued_by: str
    tenant_id: str = "default"
    user_id: Optional[str] = None
    status: LegalHoldStatus = LegalHoldStatus.ACTIVE
    scope: str = "user"  # "user", "tenant", "workspace"
    created_at: float = field(default_factory=time.time)
    released_at: Optional[float] = None
    released_by: Optional[str] = None
    release_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LegalHoldManager:
    """
    Manages active preservation orders and legal holds (Feature 10.46).
    """

    def __init__(self, audit_ledger: Optional[Any] = None):
        self.ledger = audit_ledger
        self._holds: Dict[str, LegalHoldRecord] = {}

    def place_hold(
        self,
        matter_name: str,
        issued_by: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        scope: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LegalHoldRecord:
        """Places an active legal hold on a user or tenant, freezing erasure rights."""
        hold_id = f"lh_{uuid4().hex[:12]}"
        record = LegalHoldRecord(
            hold_id=hold_id,
            matter_name=matter_name,
            issued_by=issued_by,
            tenant_id=tenant_id,
            user_id=user_id,
            status=LegalHoldStatus.ACTIVE,
            scope=scope,
            metadata=metadata or {},
        )
        self._holds[hold_id] = record

        if self.ledger and hasattr(self.ledger, "log"):
            from control.safety.audit.models import UnifiedAuditEntry, UserRole, AuditSeverity
            self.ledger.log(UnifiedAuditEntry(
                module="legal",
                action="legal_hold_placed",
                resource=f"hold:{hold_id}",
                role=UserRole.ADMIN.value,
                tenant_id=tenant_id,
                user_id=user_id,
                severity=AuditSeverity.WARNING,
                details={"matter": matter_name, "issued_by": issued_by, "scope": scope},
            ))

        return record

    def release_hold(
        self,
        hold_id: str,
        released_by: str,
        reason: str,
    ) -> LegalHoldRecord:
        """Releases an active legal hold once litigation or investigation concludes."""
        if hold_id not in self._holds:
            raise KeyError(f"Legal hold '{hold_id}' not found")

        record = self._holds[hold_id]
        record.status = LegalHoldStatus.RELEASED
        record.released_at = time.time()
        record.released_by = released_by
        record.release_reason = reason

        if self.ledger and hasattr(self.ledger, "log"):
            from control.safety.audit.models import UnifiedAuditEntry, UserRole, AuditSeverity
            self.ledger.log(UnifiedAuditEntry(
                module="legal",
                action="legal_hold_released",
                resource=f"hold:{hold_id}",
                role=UserRole.ADMIN.value,
                tenant_id=record.tenant_id,
                user_id=record.user_id,
                severity=AuditSeverity.INFO,
                details={"hold_id": hold_id, "released_by": released_by, "reason": reason},
            ))

        return record

    def is_held(self, user_id: Optional[str] = None, tenant_id: str = "default") -> bool:
        """Fast check whether an identity or tenant is currently under an active hold."""
        for hold in self._holds.values():
            if hold.status != LegalHoldStatus.ACTIVE:
                continue
            if hold.tenant_id == tenant_id:
                if hold.scope == "tenant":
                    return True
                if user_id and hold.user_id == user_id:
                    return True
        return False

    def assert_not_held(self, user_id: Optional[str] = None, tenant_id: str = "default") -> None:
        """Raises LegalHoldActiveError if the user or tenant has an active hold."""
        for hold in self._holds.values():
            if hold.status != LegalHoldStatus.ACTIVE:
                continue
            if hold.tenant_id == tenant_id:
                if hold.scope == "tenant" or (user_id and hold.user_id == user_id):
                    raise LegalHoldActiveError(
                        f"Active legal hold in place for {user_id or tenant_id} "
                        f"(Matter: '{hold.matter_name}', Hold ID: {hold.hold_id}). Deletion suspended."
                    )

    def get_active_holds(
        self,
        user_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> List[LegalHoldRecord]:
        results = []
        for hold in self._holds.values():
            if hold.status != LegalHoldStatus.ACTIVE:
                continue
            if hold.tenant_id == tenant_id:
                if hold.scope == "tenant" or (user_id and hold.user_id == user_id):
                    results.append(hold)
        return results


# Global singleton instance
default_legal_hold_manager = LegalHoldManager()

