"""
Tests for Legal Hold & Lawful Request Handler (10.46, 10.47)
Verifies erasure suspension, lawful subpoena/court order ingestion,
and cryptographic compliance audit trails.
"""

import pytest
from control.safety.legal.legal_hold import (
    LegalHoldManager,
    LegalHoldStatus,
    default_legal_hold_manager,
)
from control.safety.legal.authority_request import (
    AuthorityRequestHandler,
    RequestType,
)
from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.privacy.erasure_propagator import (
    LegalHoldActiveError,
    UniversalMemoryErasurePropagator,
)
from control.identity.lifecycle.account_manager import AccountLifecycleManager


@pytest.fixture
def ledger():
    return UnifiedAuditLedger(db_path=":memory:")


@pytest.fixture
def hold_manager(ledger):
    return LegalHoldManager(audit_ledger=ledger)


@pytest.fixture
def authority_handler(ledger, hold_manager):
    return AuthorityRequestHandler(audit_ledger=ledger, legal_hold_manager=hold_manager)


def test_place_and_release_legal_hold(hold_manager):
    user_id = "user_investigation_target"
    record = hold_manager.place_hold(
        matter_name="SEC v. Alpha Trading",
        issued_by="Chief Compliance Officer",
        user_id=user_id,
        tenant_id="tenant_securities",
    )

    assert record.status == LegalHoldStatus.ACTIVE
    assert hold_manager.is_held(user_id=user_id, tenant_id="tenant_securities") is True

    # Other users not held
    assert hold_manager.is_held(user_id="user_unrelated", tenant_id="tenant_securities") is False

    # Release hold
    released = hold_manager.release_hold(
        hold_id=record.hold_id,
        released_by="Compliance Committee",
        reason="Matter resolved with no adverse findings",
    )
    assert released.status == LegalHoldStatus.RELEASED
    assert hold_manager.is_held(user_id=user_id, tenant_id="tenant_securities") is False


def test_user_with_legal_hold_cannot_erase(hold_manager, ledger):
    """Acceptance Test: User with legal hold cannot erase."""
    user_id = "user_litigation_hold"
    hold_manager.place_hold(
        matter_name="DOJ Antitrust Preservation Order",
        issued_by="US District Court",
        user_id=user_id,
        tenant_id="tenant_corp",
    )

    propagator = UniversalMemoryErasurePropagator(
        audit_ledger=ledger,
        legal_hold_handler=hold_manager,
    )

    with pytest.raises(LegalHoldActiveError) as exc_info:
        propagator.propagate_erasure(user_id=user_id, tenant_id="tenant_corp")

    assert "active legal hold" in str(exc_info.value).lower()
    assert "DOJ Antitrust Preservation Order" in str(exc_info.value)


def test_account_closure_blocked_by_legal_hold():
    # Use default singleton which account_manager references
    user_id = "user_trying_to_flee"
    default_legal_hold_manager.place_hold(
        matter_name="Subpoena: State AG Inquiry",
        issued_by="Attorney General",
        user_id=user_id,
    )

    account_mgr = AccountLifecycleManager()
    account_mgr.create_account(user_id=user_id, email="fugitive@example.com")

    # Attempting to schedule closure must be blocked
    with pytest.raises(PermissionError) as exc_info:
        account_mgr.request_account_closure(user_id=user_id)

    assert "active legal hold" in str(exc_info.value).lower()

    # Clean up singleton
    default_legal_hold_manager._holds.clear()


def test_authority_request_logged_with_full_audit(authority_handler, ledger, hold_manager):
    """Acceptance Test: Authority request logged with full audit."""
    target_user = "user_subpoena_target_42"

    req_record, hold_record = authority_handler.record_request(
        request_type=RequestType.SUBPOENA,
        issuing_authority="United States District Court for the Southern District of New York",
        case_number="1:26-cv-09142",
        target_user_id=target_user,
        target_tenant_id="tenant_enterprise",
        auto_place_legal_hold=True,
    )

    assert req_record.request_type == RequestType.SUBPOENA
    assert len(req_record.audit_hash) == 64
    assert hold_record is not None
    assert hold_record.user_id == target_user
    assert hold_manager.is_held(user_id=target_user, tenant_id="tenant_enterprise") is True

    # Verify audit ledger recorded the event
    events = ledger.query(module="legal", action="lawful_authority_request_received")
    assert len(events) == 1
    event = events[0]
    assert event.details["case_number"] == "1:26-cv-09142"
    assert event.details["issuing_authority"] == req_record.issuing_authority

    # Verify cryptographic hash chain integrity
    assert ledger.verify_chain() is True


def test_authority_request_fulfillment_and_export(authority_handler, ledger):
    req_record, _ = authority_handler.record_request(
        request_type=RequestType.COURT_ORDER,
        issuing_authority="Munich Regional Court",
        case_number="AZ 12 O 458/26",
        target_user_id="user_munich_case",
        target_tenant_id="tenant_eu",
    )

    fulfilled = authority_handler.fulfill_request(
        request_id=req_record.request_id,
        fulfillment_notes="Exported relevant audit bundles under court order",
    )
    assert fulfilled.status == "fulfilled"

    trail = authority_handler.export_audit_trail(req_record.request_id)
    assert trail["chain_valid"] is True
    assert trail["request"]["case"] == "AZ 12 O 458/26"
    assert len(trail["audit_events"]) >= 2

