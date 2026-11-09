"""Tests for Account Lifecycle Management (Task 12.9)."""

import pytest
import time
from control.identity.lifecycle.account_manager import (
    AccountLifecycleManager,
    AccountStatus,
)


def test_account_lifecycle_recovery_merge_closure_acceptance():
    """Acceptance Test: User can recover account via email; two accounts can be merged; deleted account has 30-day grace period."""
    mgr = AccountLifecycleManager()

    # Create primary and secondary user accounts
    acc_primary = mgr.create_account("usr_1", "user1@enterprise.org", password_hash="hash_old")
    acc_secondary = mgr.create_account("usr_2", "user2@personal.net", password_hash="hash_p2")

    # 1. User can recover account via email
    token = mgr.initiate_recovery("user1@enterprise.org")
    assert token.startswith("rec_")
    assert acc_primary.status == AccountStatus.RECOVERY_PENDING

    # Complete recovery
    recovered = mgr.complete_recovery(token, new_password_hash="hash_new_secure")
    assert recovered.status == AccountStatus.ACTIVE
    assert recovered.password_hash == "hash_new_secure"

    # 2. Two accounts can be merged
    merged_target = mgr.merge_accounts(source_user_id="usr_2", target_user_id="usr_1")
    assert merged_target.user_id == "usr_1"

    source_acc = mgr.get_account("usr_2")
    assert source_acc.status == AccountStatus.MERGED
    assert source_acc.merged_into == "usr_1"

    # 3. Deleted account has 30-day grace period
    mgr.request_account_closure(user_id="usr_1", grace_period_days=30)
    acc_closing = mgr.get_account("usr_1")
    assert acc_closing.status == AccountStatus.PENDING_DELETION
    assert acc_closing.deletion_effective_at is not None
    # Verify ~30 days (2,592,000s)
    remaining_secs = acc_closing.deletion_effective_at - acc_closing.deletion_requested_at
    assert remaining_secs == pytest.approx(30 * 86400, rel=1e-3)

    # Cancel closure within grace period
    restored = mgr.cancel_account_closure("usr_1")
    assert restored.status == AccountStatus.ACTIVE
    assert restored.deletion_effective_at is None
