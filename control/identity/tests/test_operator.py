"""Tests for Operator Console & Audited Support Impersonation (Task 12.11)."""

import pytest
from control.identity.operator.console import OperatorConsole
from control.identity.operator.impersonation import ImpersonationManager
from control.safety.audit.ledger import UnifiedAuditLedger


def test_operator_console_pause_and_impersonation_acceptance():
    """Acceptance Test: Admin can pause all agent actions for a user; admin can impersonate user with audit log entry."""
    console = OperatorConsole()
    ledger = UnifiedAuditLedger(db_path=":memory:")
    imp_mgr = ImpersonationManager(audit_ledger=ledger)

    target_user = "user_troubled_101"
    admin_id = "admin_super_ops"

    # 1. Admin can pause all agent actions for a user
    assert console.is_execution_allowed(user_id=target_user) is True

    intervention = console.pause_user_agents(
        user_id=target_user,
        admin_id=admin_id,
        reason="Abnormal token consumption loop detected",
    )
    assert intervention.state.value == "paused"
    assert console.is_execution_allowed(user_id=target_user) is False

    # Resume
    console.resume_user_agents(user_id=target_user, admin_id=admin_id)
    assert console.is_execution_allowed(user_id=target_user) is True

    # 2. Admin can impersonate user with immutable audit log entry
    imp_session = imp_mgr.start_impersonation(
        admin_id=admin_id,
        target_user_id=target_user,
        reason="Investigating broken custom agent prompt",
        support_ticket_id="TICKET-7788",
        duration_minutes=30,
    )
    assert imp_session.is_active is True
    assert imp_session.admin_id == admin_id
    assert imp_session.target_user_id == target_user

    # End impersonation
    assert imp_mgr.end_impersonation(imp_session.session_id) is True
    assert imp_mgr.is_session_active(imp_session.session_id) is False

    # 3. Verify audit log recorded in Merkle ledger
    integrity_valid = ledger.verify_integrity()
    assert integrity_valid is True

    entries = ledger.query(module="operator.impersonation")
    actions = [e.action for e in entries]
    assert "impersonation_started" in actions
    assert "impersonation_ended" in actions
    start_entry = next(e for e in entries if e.action == "impersonation_started")
    assert start_entry.details["support_ticket"] == "TICKET-7788"
