"""
Tests for Account Lifecycle Grace Period & Auto-Erasure (Features 10.51, 10.52).
"""

import time
import pytest
from unittest.mock import MagicMock

from control.safety.lifecycle.grace_period import (
    AccountGracePeriodManager,
    GracePeriodExpiredError,
    GracePeriodStatus,
)
from control.identity.lifecycle.account_manager import AccountLifecycleManager, AccountStatus


def test_soft_delete_and_recovery_within_grace_period():
    mgr = AccountGracePeriodManager(default_grace_days=30)
    user_id = "user_test_recovery"

    # Request soft deletion
    record = mgr.request_soft_delete(user_id=user_id, grace_days=30, reason="User requested deletion")
    assert record.status == GracePeriodStatus.PENDING_DELETION
    assert record.expires_at > record.requested_at

    # Status check
    status = mgr.get_status(user_id)
    assert status["is_recoverable"] is True
    assert status["status"] == "pending_deletion"
    assert 29.0 <= status["remaining_days"] <= 30.0

    # Recover within grace period (simulated at day 15)
    simulated_recovery_time = record.requested_at + (15 * 86400)
    recovered_record = mgr.recover_account(user_id, current_time=simulated_recovery_time)
    assert recovered_record.status == GracePeriodStatus.RECOVERED

    # Check status after recovery
    status_after = mgr.get_status(user_id)
    assert status_after["status"] == "recovered"
    assert status_after["is_recoverable"] is False


def test_recovery_fails_after_30_day_grace_period():
    mgr = AccountGracePeriodManager(default_grace_days=30)
    user_id = "user_expired_recovery"

    record = mgr.request_soft_delete(user_id=user_id, grace_days=30)
    simulated_expired_time = record.expires_at + 100  # Past expiration

    with pytest.raises(GracePeriodExpiredError):
        mgr.recover_account(user_id, current_time=simulated_expired_time)

    status = mgr.get_status(user_id, current_time=simulated_expired_time)
    assert status["is_recoverable"] is False
    assert status["status"] == "expired"


def test_process_expired_accounts_triggers_erasure_propagator():
    mock_propagator = MagicMock()
    mock_receipt = MagicMock()
    mock_receipt.audit_meta_record_hash = "mock_hash_123"
    mock_propagator.propagate_erasure.return_value = mock_receipt

    mgr = AccountGracePeriodManager(erasure_propagator=mock_propagator, default_grace_days=30)

    # User 1: 30-day grace, now expired
    user1 = "user_auto_erase_1"
    rec1 = mgr.request_soft_delete(user_id=user1, tenant_id="tenant_a", grace_days=30)

    # User 2: not yet expired (60-day grace window)
    user2 = "user_still_active_2"
    rec2 = mgr.request_soft_delete(user_id=user2, tenant_id="tenant_a", grace_days=60)

    current_time = rec1.requested_at + (31 * 86400)  # 31 days passed

    receipts = mgr.process_expired_accounts(current_time=current_time)
    assert len(receipts) == 1
    assert receipts[0] == mock_receipt

    # Verify mock_propagator was called for user1, but not user2
    mock_propagator.propagate_erasure.assert_called_once()
    called_kwargs = mock_propagator.propagate_erasure.call_args[1]
    assert called_kwargs["user_id"] == user1
    assert called_kwargs["tenant_id"] == "tenant_a"

    # Status of user1 is now permanently closed
    assert mgr.get_status(user1)["status"] == "permanently_closed"
    # Status of user2 is still pending deletion
    assert mgr.get_status(user2, current_time=current_time)["status"] == "pending_deletion"


def test_integration_with_account_lifecycle_manager():
    lifecycle_mgr = AccountLifecycleManager()
    user_id = "user_integration"
    lifecycle_mgr.create_account(user_id=user_id, email="integration@example.com")

    grace_mgr = AccountGracePeriodManager(account_lifecycle_manager=lifecycle_mgr, default_grace_days=30)

    # Soft delete via grace manager
    grace_mgr.request_soft_delete(user_id=user_id, grace_days=30)
    acc = lifecycle_mgr.get_account(user_id)
    assert acc.status == AccountStatus.PENDING_DELETION

    # Recover via grace manager
    grace_mgr.recover_account(user_id=user_id)
    acc = lifecycle_mgr.get_account(user_id)
    assert acc.status == AccountStatus.ACTIVE


def test_legal_hold_blocks_soft_deletion():
    from control.safety.legal.legal_hold import LegalHoldManager
    hold_mgr = LegalHoldManager()
    hold_mgr.place_hold(
        matter_name="SEC Compliance Audit",
        issued_by="US-SEC",
        user_id="user_under_hold",
    )

    # Monkeypatch singleton
    from control.safety.legal import legal_hold
    original_mgr = legal_hold.default_legal_hold_manager
    legal_hold.default_legal_hold_manager = hold_mgr

    try:
        grace_mgr = AccountGracePeriodManager()
        with pytest.raises(PermissionError) as exc_info:
            grace_mgr.request_soft_delete(user_id="user_under_hold")
        assert "active legal hold" in str(exc_info.value)
    finally:
        legal_hold.default_legal_hold_manager = original_mgr
