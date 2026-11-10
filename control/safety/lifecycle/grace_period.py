"""
Account Lifecycle Grace Period & Automated Erasure Enforcer (Features 10.51, 10.52).

Features:
- 10.51: Soft-deletion lifecycle with 30-day grace period. Account can be recovered
  within 30 days without loss of data.
- 10.52: Automated expiration runner: upon lapse of the 30-day grace period, automatically
  triggers the Universal Memory Erasure Propagator (Feature 10.31) to wipe all cognitive memory,
  indexes, caches, and PII stores permanently.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("control.safety.lifecycle.grace_period")


class GracePeriodStatus(str, Enum):
    ACTIVE = "active"
    PENDING_DELETION = "pending_deletion"
    EXPIRED = "expired"
    RECOVERED = "recovered"
    PERMANENTLY_CLOSED = "permanently_closed"


class GracePeriodExpiredError(PermissionError):
    """Raised when an attempt is made to recover an account whose grace period has expired."""
    pass


class GracePeriodAlreadyActiveError(ValueError):
    """Raised when requesting closure for an account already pending deletion."""
    pass


@dataclass
class GracePeriodRecord:
    """Tracks account soft-deletion window and expiration."""
    user_id: str
    tenant_id: str = "default"
    requested_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 30 * 86400)
    status: GracePeriodStatus = GracePeriodStatus.PENDING_DELETION
    reason: str = "User requested account closure"
    metadata: Dict[str, Any] = field(default_factory=dict)
    erasure_receipt_id: Optional[str] = None


class AccountGracePeriodManager:
    """
    Manages soft-deletion retention windows and coordinates with Universal Memory Erasure Propagator.
    """

    def __init__(
        self,
        account_lifecycle_manager: Optional[Any] = None,
        erasure_propagator: Optional[Any] = None,
        default_grace_days: int = 30,
    ) -> None:
        self.default_grace_days = default_grace_days
        self._lifecycle_mgr = account_lifecycle_manager
        self._erasure_propagator = erasure_propagator
        self._records: Dict[str, GracePeriodRecord] = {}  # user_id -> record

    def _get_lifecycle_mgr(self) -> Any:
        if self._lifecycle_mgr is None:
            try:
                from control.identity.lifecycle.account_manager import default_account_lifecycle_manager
                self._lifecycle_mgr = default_account_lifecycle_manager
            except ImportError:
                pass
        return self._lifecycle_mgr

    def _get_erasure_propagator(self) -> Any:
        if self._erasure_propagator is None:
            try:
                from control.safety.privacy.erasure_propagator import default_erasure_propagator
                self._erasure_propagator = default_erasure_propagator
            except ImportError:
                pass
        return self._erasure_propagator

    def request_soft_delete(
        self,
        user_id: str,
        tenant_id: str = "default",
        grace_days: Optional[int] = None,
        reason: str = "User requested account closure",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GracePeriodRecord:
        """
        Initiates a soft-delete on the account with a 30-day grace period (Feature 10.51).
        Checks for active legal holds before proceeding.
        """
        # Legal hold check
        try:
            from control.safety.legal.legal_hold import default_legal_hold_manager
            if default_legal_hold_manager and default_legal_hold_manager.is_held(user_id=user_id):
                raise PermissionError(f"Account deletion prohibited: User '{user_id}' is under an active legal hold.")
        except ImportError:
            pass

        now = time.time()
        days = grace_days if grace_days is not None else self.default_grace_days
        expires_at = now + (days * 86400)

        record = GracePeriodRecord(
            user_id=user_id,
            tenant_id=tenant_id,
            requested_at=now,
            expires_at=expires_at,
            status=GracePeriodStatus.PENDING_DELETION,
            reason=reason,
            metadata=metadata or {},
        )
        self._records[user_id] = record

        # Forward to AccountLifecycleManager if available
        mgr = self._get_lifecycle_mgr()
        if mgr and hasattr(mgr, "request_account_closure"):
            try:
                mgr.request_account_closure(user_id=user_id, grace_period_days=days)
            except KeyError:
                # If account is not in Identity store (e.g. standalone test), keep local record
                pass

        logger.info(
            "Account '%s' (tenant '%s') soft-deleted with %d-day grace period until %.0f",
            user_id,
            tenant_id,
            days,
            expires_at,
        )
        return record

    def recover_account(self, user_id: str, current_time: Optional[float] = None) -> GracePeriodRecord:
        """
        Recovers a soft-deleted account within the grace period (Feature 10.51).
        Raises GracePeriodExpiredError if the window has passed.
        """
        record = self._records.get(user_id)
        if not record:
            raise KeyError(f"No grace period record found for user '{user_id}'")

        if record.status == GracePeriodStatus.PERMANENTLY_CLOSED:
            raise GracePeriodExpiredError(f"Account '{user_id}' has already been permanently erased.")

        now = current_time if current_time is not None else time.time()
        if now > record.expires_at:
            record.status = GracePeriodStatus.EXPIRED
            raise GracePeriodExpiredError(
                f"Grace period for account '{user_id}' expired at {record.expires_at} (current: {now}). Account cannot be recovered."
            )

        record.status = GracePeriodStatus.RECOVERED

        # Restore in Identity lifecycle manager
        mgr = self._get_lifecycle_mgr()
        if mgr and hasattr(mgr, "cancel_account_closure"):
            try:
                mgr.cancel_account_closure(user_id=user_id)
            except (KeyError, ValueError):
                pass

        logger.info("Account '%s' successfully recovered within grace period.", user_id)
        return record

    def get_status(self, user_id: str, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Retrieves detailed grace status, remaining time, and recoverability.
        """
        record = self._records.get(user_id)
        if not record:
            return {"user_id": user_id, "status": GracePeriodStatus.ACTIVE.value, "is_recoverable": False}

        now = current_time if current_time is not None else time.time()
        remaining_seconds = max(0.0, record.expires_at - now)
        is_expired = now > record.expires_at and record.status == GracePeriodStatus.PENDING_DELETION

        current_status = record.status
        if is_expired:
            current_status = GracePeriodStatus.EXPIRED

        return {
            "user_id": user_id,
            "tenant_id": record.tenant_id,
            "status": current_status.value,
            "requested_at": record.requested_at,
            "expires_at": record.expires_at,
            "remaining_seconds": remaining_seconds,
            "remaining_days": round(remaining_seconds / 86400, 2),
            "is_recoverable": current_status == GracePeriodStatus.PENDING_DELETION and remaining_seconds > 0,
            "reason": record.reason,
        }

    def process_expired_accounts(
        self,
        current_time: Optional[float] = None,
    ) -> List[Any]:
        """
        Scans all pending-deletion accounts. If the grace period has elapsed,
        triggers the Universal Memory Erasure Propagator (Feature 10.52 / 10.31).
        """
        now = current_time if current_time is not None else time.time()
        erasure_receipts = []
        propagator = self._get_erasure_propagator()

        for user_id, record in list(self._records.items()):
            if record.status == GracePeriodStatus.PENDING_DELETION and now >= record.expires_at:
                logger.warning(
                    "Grace period expired for account '%s'. Triggering permanent memory erasure cascade.",
                    user_id,
                )
                record.status = GracePeriodStatus.PERMANENTLY_CLOSED

                receipt = None
                if propagator and hasattr(propagator, "propagate_erasure"):
                    receipt = propagator.propagate_erasure(
                        user_id=user_id,
                        tenant_id=record.tenant_id,
                        reason=f"Account lifecycle 30-day grace period expired: {record.reason}",
                    )
                    if hasattr(receipt, "audit_meta_record_hash"):
                        record.erasure_receipt_id = receipt.audit_meta_record_hash
                    erasure_receipts.append(receipt)

                # Sync with Identity manager
                mgr = self._get_lifecycle_mgr()
                if mgr and hasattr(mgr, "permanently_close_and_erase"):
                    try:
                        mgr.permanently_close_and_erase(user_id=user_id, erasure_propagator=propagator)
                    except KeyError:
                        pass

        return erasure_receipts

    def list_pending(self) -> List[GracePeriodRecord]:
        return [r for r in self._records.values() if r.status == GracePeriodStatus.PENDING_DELETION]


# Default singleton
default_grace_period_manager = AccountGracePeriodManager()

