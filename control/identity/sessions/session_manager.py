"""Session Management, Forced Logout & Tamper-Evident Identity Audit (Layer 12: IAM, Task 12.8).

Features:
- 12.39: Session management & active device enumeration
- 12.40: Administrative forced session logout & revocation
- 12.41: Identity audit log with cryptographic hash chain bridging to L10 Merkle Ledger
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.audit.models import AuditSeverity, UnifiedAuditEntry, UserRole

logger = logging.getLogger("control.identity.sessions")


@dataclass
class UserSession:
    """Active user session representation."""
    session_id: str
    user_id: str
    tenant_id: str
    device_name: str
    client_ip: str
    user_agent: str
    created_at: float
    last_active: float
    is_active: bool = True


class IdentitySessionManager:
    """Manages active user sessions, forced termination, and tamper-evident audit logging."""

    def __init__(self, audit_ledger: Optional[UnifiedAuditLedger] = None):
        self._sessions: Dict[str, UserSession] = {}  # session_id -> session
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> list of session_ids
        self.ledger = audit_ledger or UnifiedAuditLedger(db_path=":memory:")

    def create_session(
        self,
        user_id: str,
        tenant_id: str = "default",
        device_name: str = "Desktop Browser",
        client_ip: str = "127.0.0.1",
        user_agent: str = "Mozilla/5.0",
    ) -> UserSession:
        now = time.time()
        s_id = f"sess_{secrets.token_hex(16)}"
        session = UserSession(
            session_id=s_id,
            user_id=user_id,
            tenant_id=tenant_id,
            device_name=device_name,
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=now,
            last_active=now,
            is_active=True,
        )
        self._sessions[s_id] = session
        self._user_sessions.setdefault(user_id, []).append(s_id)

        # Audit event to L10 Merkle ledger
        self._audit_identity_event(
            user_id=user_id,
            tenant_id=tenant_id,
            action="session_created",
            details={"session_id": s_id, "device": device_name, "ip": client_ip},
            client_ip=client_ip,
        )
        return session

    def list_active_sessions(self, user_id: str) -> List[UserSession]:
        s_ids = self._user_sessions.get(user_id, [])
        return [self._sessions[sid] for sid in s_ids if sid in self._sessions and self._sessions[sid].is_active]

    def terminate_session(self, session_id: str, terminated_by: str = "user") -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return False

        session.is_active = False
        self._audit_identity_event(
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            action="session_terminated",
            details={"session_id": session_id, "terminated_by": terminated_by},
            client_ip=session.client_ip,
        )
        return True

    def force_logout_user(self, user_id: str, admin_user_id: str, reason: str = "Administrative Security Action") -> int:
        """Administrative forced logout: terminates all active sessions for a user (12.40)."""
        active_sessions = self.list_active_sessions(user_id)
        count = 0
        for s in active_sessions:
            s.is_active = False
            count += 1

        self._audit_identity_event(
            user_id=user_id,
            tenant_id=active_sessions[0].tenant_id if active_sessions else "default",
            action="force_logout_all",
            details={"revoked_count": count, "admin_user_id": admin_user_id, "reason": reason},
            severity=AuditSeverity.WARNING,
        )
        return count

    def is_session_valid(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        if not session.is_active:
            return False
        # Optional: check idle timeout (e.g., 24 hours)
        if time.time() - session.last_active > 86400:
            session.is_active = False
            return False
        session.last_active = time.time()
        return True

    def _audit_identity_event(
        self,
        user_id: str,
        tenant_id: str,
        action: str,
        details: Dict[str, Any],
        client_ip: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> UnifiedAuditEntry:
        """Appends tamper-evident audit entry into L10 Merkle Ledger (12.41)."""
        entry = UnifiedAuditEntry(
            id=f"idaud-{secrets.token_hex(8)}",
            tenant_id=tenant_id,
            user_id=user_id,
            module="identity",
            action=action,
            severity=severity,
            details=details,
            client_ip=client_ip,
        )
        self.ledger.log(entry)
        return entry
