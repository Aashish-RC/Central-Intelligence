"""Audited Support Impersonation (Layer 12: IAM, Feature 12.47).

Allows authorized administrators/support engineers to act on behalf of a user
under strict, immutable, tamper-evident audit logging.
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.audit.models import AuditSeverity, UnifiedAuditEntry

logger = logging.getLogger("control.identity.operator_console.impersonation")


@dataclass
class ImpersonationSession:
    """Scoped support impersonation session."""
    session_id: str
    admin_id: str
    target_user_id: str
    tenant_id: str
    reason: str
    support_ticket_id: str
    started_at: float
    expires_at: float
    is_active: bool = True


class ImpersonationManager:
    """Coordinates audited administrative user impersonation."""

    def __init__(self, audit_ledger: Optional[UnifiedAuditLedger] = None):
        self._sessions: Dict[str, ImpersonationSession] = {}
        self.ledger = audit_ledger or UnifiedAuditLedger(db_path=":memory:")

    def start_impersonation(
        self,
        admin_id: str,
        target_user_id: str,
        reason: str,
        support_ticket_id: str,
        tenant_id: str = "default",
        duration_minutes: int = 60,
    ) -> ImpersonationSession:
        """Starts an audited impersonation session (12.47)."""
        now = time.time()
        s_id = f"imp_{secrets.token_hex(12)}"
        session = ImpersonationSession(
            session_id=s_id,
            admin_id=admin_id,
            target_user_id=target_user_id,
            tenant_id=tenant_id,
            reason=reason,
            support_ticket_id=support_ticket_id,
            started_at=now,
            expires_at=now + (duration_minutes * 60),
            is_active=True,
        )
        self._sessions[s_id] = session

        # Log high-severity audit record to L10 Merkle ledger
        entry = UnifiedAuditEntry(
            id=f"aud-{s_id}",
            tenant_id=tenant_id,
            user_id=admin_id,
            module="operator.impersonation",
            action="impersonation_started",
            severity=AuditSeverity.WARNING,
            details={
                "target_user_id": target_user_id,
                "support_ticket": support_ticket_id,
                "reason": reason,
                "session_id": s_id,
                "duration_minutes": duration_minutes,
            },
        )
        self.ledger.log(entry)
        logger.warning(f"Admin {admin_id} started impersonation of {target_user_id} (ticket: {support_ticket_id})")
        return session

    def end_impersonation(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return False

        session.is_active = False
        entry = UnifiedAuditEntry(
            id=f"aud-end-{session_id}",
            tenant_id=session.tenant_id,
            user_id=session.admin_id,
            module="operator.impersonation",
            action="impersonation_ended",
            severity=AuditSeverity.INFO,
            details={"session_id": session_id, "target_user_id": session.target_user_id},
        )
        self.ledger.log(entry)
        return True

    def is_session_active(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return False
        if time.time() > session.expires_at:
            session.is_active = False
            return False
        return True

