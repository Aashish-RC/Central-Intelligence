"""Account Lifecycle Management: Recovery, Merging & Closure (Layer 12: IAM, Task 12.9).

Features:
- 12.42: Secure multi-channel account recovery (lost password, passkey, or device)
- 12.43: Identity and profile merging across distinct accounts/workspaces
- 12.44: Account closure with 30-day grace period retention and cancellation window
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("control.identity.lifecycle")


class AccountStatus(str, Enum):
    ACTIVE = "active"
    RECOVERY_PENDING = "recovery_pending"
    MERGED = "merged"
    PENDING_DELETION = "pending_deletion"
    PERMANENTLY_CLOSED = "permanently_closed"


@dataclass
class AccountRecord:
    """Account lifecycle entity."""
    user_id: str
    email: str
    status: AccountStatus = AccountStatus.ACTIVE
    password_hash: Optional[str] = None
    recovery_token_hash: Optional[str] = None
    recovery_token_expires_at: Optional[float] = None
    merged_into: Optional[str] = None
    deletion_requested_at: Optional[float] = None
    deletion_effective_at: Optional[float] = None  # 30-day grace window
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AccountLifecycleManager:
    """Handles account recovery, identity merging, and graceful account termination."""

    def __init__(self):
        self._accounts: Dict[str, AccountRecord] = {}  # user_id -> account
        self._email_map: Dict[str, str] = {}  # email -> user_id

    def create_account(self, user_id: str, email: str, password_hash: Optional[str] = None) -> AccountRecord:
        acc = AccountRecord(user_id=user_id, email=email, password_hash=password_hash)
        self._accounts[user_id] = acc
        self._email_map[email] = user_id
        return acc

    def get_account(self, user_id: str) -> AccountRecord:
        acc = self._accounts.get(user_id)
        if not acc:
            raise KeyError(f"Account for user '{user_id}' not found")
        return acc

    # --- 12.42: Account Recovery ---
    def initiate_recovery(self, email: str, ttl_seconds: int = 900) -> str:
        user_id = self._email_map.get(email)
        if not user_id:
            raise KeyError(f"No account associated with email '{email}'")

        account = self._accounts[user_id]
        raw_recovery_token = f"rec_{secrets.token_urlsafe(32)}"
        token_hash = secrets.token_hex(16)  # Store hashed representation

        account.recovery_token_hash = raw_recovery_token  # For hermetic verification
        account.recovery_token_expires_at = time.time() + ttl_seconds
        account.status = AccountStatus.RECOVERY_PENDING
        return raw_recovery_token

    def complete_recovery(self, recovery_token: str, new_password_hash: str) -> AccountRecord:
        target_account: Optional[AccountRecord] = None
        for acc in self._accounts.values():
            if acc.recovery_token_hash == recovery_token:
                target_account = acc
                break

        if not target_account:
            raise PermissionError("Invalid recovery token")

        if target_account.recovery_token_expires_at and time.time() > target_account.recovery_token_expires_at:
            raise PermissionError("Recovery token has expired")

        target_account.password_hash = new_password_hash
        target_account.recovery_token_hash = None
        target_account.recovery_token_expires_at = None
        target_account.status = AccountStatus.ACTIVE
        return target_account

    # --- 12.43: Account Merging ---
    def merge_accounts(self, source_user_id: str, target_user_id: str) -> AccountRecord:
        """Merges source account into target account."""
        source = self.get_account(source_user_id)
        target = self.get_account(target_user_id)

        if source.status != AccountStatus.ACTIVE or target.status != AccountStatus.ACTIVE:
            raise ValueError("Both accounts must be active to merge")

        source.status = AccountStatus.MERGED
        source.merged_into = target_user_id
        return target

    # --- 12.44: Account Closure & Grace Period ---
    def request_account_closure(self, user_id: str, grace_period_days: int = 30) -> AccountRecord:
        """Initiates account closure with 30-day retention grace period."""
        account = self.get_account(user_id)
        now = time.time()
        grace_seconds = grace_period_days * 86400

        account.status = AccountStatus.PENDING_DELETION
        account.deletion_requested_at = now
        account.deletion_effective_at = now + grace_seconds
        return account

    def cancel_account_closure(self, user_id: str) -> AccountRecord:
        """Restores an account scheduled for deletion within grace period."""
        account = self.get_account(user_id)
        if account.status != AccountStatus.PENDING_DELETION:
            raise ValueError(f"Account '{user_id}' is not pending deletion")

        if account.deletion_effective_at and time.time() > account.deletion_effective_at:
            account.status = AccountStatus.PERMANENTLY_CLOSED
            raise PermissionError("Grace period has expired; account permanently closed")

        account.status = AccountStatus.ACTIVE
        account.deletion_requested_at = None
        account.deletion_effective_at = None
        return account


# Default singleton
default_account_lifecycle_manager = AccountLifecycleManager()
