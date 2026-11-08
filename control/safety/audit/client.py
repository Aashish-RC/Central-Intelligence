"""
Unified audit logging client and global singleton helper.
"""

import os
from typing import Any, Dict, Optional, Union
from .models import UnifiedAuditEntry, AuditSeverity, UserRole
from .ledger import UnifiedAuditLedger

_GLOBAL_LOGGER: Optional["AuditLogger"] = None


class AuditLogger:
    """Thread-safe emitter for cross-module audit logging."""

    def __init__(self, ledger: Optional[UnifiedAuditLedger] = None):
        if ledger is not None:
            self.ledger = ledger
        else:
            db_path = os.getenv("PHEONIX_AUDIT_DB", "./data/unified_audit.db")
            self.ledger = UnifiedAuditLedger(db_path=db_path)

    def record(
        self,
        module: str,
        action: str,
        tenant_id: str = "default",
        project_id: str = "default",
        user_id: Optional[str] = None,
        role: Union[UserRole, str] = UserRole.SYSTEM.value,
        resource: str = "",
        status: str = "success",
        severity: AuditSeverity = AuditSeverity.INFO,
        details: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
    ) -> str:
        """Emit an audit event to the tamper-evident ledger."""
        role_val = role.value if hasattr(role, "value") else str(role)
        entry = UnifiedAuditEntry(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            role=role_val,
            module=module,
            action=action,
            resource=resource,
            status=status,
            severity=severity,
            details=details or {},
            client_ip=client_ip,
        )
        return self.ledger.log(entry)

    def query(self, **kwargs: Any):
        """Query entries from the underlying ledger."""
        return self.ledger.query(**kwargs)

    def verify_integrity(self) -> bool:
        """Verify the cryptographic hash chain of the ledger."""
        return self.ledger.verify_integrity()

    def verify_chain(self) -> bool:
        """Verify the cryptographic hash chain of the ledger."""
        return self.ledger.verify_chain()



def get_audit_logger() -> AuditLogger:
    """Return or initialize the process-wide audit logger."""
    global _GLOBAL_LOGGER
    if _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = AuditLogger()
    return _GLOBAL_LOGGER


def set_audit_logger(logger: AuditLogger) -> None:
    """Explicitly override the global audit logger (e.g. for testing with :memory:)."""
    global _GLOBAL_LOGGER
    _GLOBAL_LOGGER = logger
