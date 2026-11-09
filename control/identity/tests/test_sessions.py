"""Tests for Session Management, Forced Logout & Tamper-Evident Identity Audit (Task 12.8)."""

import pytest
from control.identity.sessions.session_manager import IdentitySessionManager
from control.safety.audit.ledger import UnifiedAuditLedger


def test_session_management_and_forced_logout_acceptance():
    """Acceptance Test: Admin can force-logout all sessions for a user; identity audit log is tamper-evident."""
    ledger = UnifiedAuditLedger(db_path=":memory:")
    session_mgr = IdentitySessionManager(audit_ledger=ledger)

    user_id = "user_victim_01"

    # 1. User logs in on two devices
    s1 = session_mgr.create_session(user_id=user_id, device_name="MacBook Chrome", client_ip="192.168.1.10")
    s2 = session_mgr.create_session(user_id=user_id, device_name="iPhone Safari", client_ip="10.0.0.5")

    active_before = session_mgr.list_active_sessions(user_id)
    assert len(active_before) == 2
    assert session_mgr.is_session_valid(s1.session_id) is True
    assert session_mgr.is_session_valid(s2.session_id) is True

    # 2. Admin performs forced logout on user
    revoked_count = session_mgr.force_logout_user(
        user_id=user_id,
        admin_user_id="admin_sec_ops",
        reason="Suspicious credential compromise suspected",
    )
    assert revoked_count == 2

    # 3. All sessions are immediately invalid
    active_after = session_mgr.list_active_sessions(user_id)
    assert len(active_after) == 0
    assert session_mgr.is_session_valid(s1.session_id) is False
    assert session_mgr.is_session_valid(s2.session_id) is False

    # 4. Verify identity audit log in L10 Merkle Ledger is tamper-evident
    integrity_valid = ledger.verify_integrity()
    assert integrity_valid is True

    # Query entries for user_victim_01
    entries = ledger.query(user_id=user_id)
    actions = [e.action for e in entries]
    assert "session_created" in actions
    assert "force_logout_all" in actions
