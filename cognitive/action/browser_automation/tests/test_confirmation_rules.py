"""Tests for ConfirmationRulesGate."""

import pytest
from browser_automation.core.models import (
    ActionRiskLevel,
    BrowserAction,
    BrowserActionType,
    ConfirmationStatus,
)
from browser_automation.engine.confirmation_rules import ConfirmationRulesGate


@pytest.fixture
def gate():
    return ConfirmationRulesGate()


def test_gate_safe_action_permits_immediately(gate):
    action = BrowserAction(
        action_type=BrowserActionType.NAVIGATE,
        url="https://docs.python.org",
    )
    permitted = gate.evaluate_and_gate(action)
    assert permitted is True
    assert action.confirmation_status == ConfirmationStatus.NOT_REQUIRED
    assert len(gate.get_pending_actions()) == 0


def test_gate_consequential_action_intercepts_and_enqueues(gate):
    action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="button.buy-now-btn",
    )
    permitted = gate.evaluate_and_gate(action)
    assert permitted is False
    assert action.risk_level == ActionRiskLevel.CONSEQUENTIAL
    assert action.confirmation_status == ConfirmationStatus.PENDING_APPROVAL
    assert len(gate.get_pending_actions()) == 1

    # Now approve the action
    gate.approve_action(action.action_id)
    assert len(gate.get_pending_actions()) == 0

    # Re-evaluating now returns permitted
    permitted_after_approval = gate.evaluate_and_gate(action)
    assert permitted_after_approval is True
    assert action.confirmation_status == ConfirmationStatus.APPROVED


def test_gate_consequential_action_rejection(gate):
    action = BrowserAction(
        action_type=BrowserActionType.DELETE_DATA,
        target_selector="button#purge-all",
    )
    permitted = gate.evaluate_and_gate(action)
    assert permitted is False

    gate.reject_action(action.action_id, reason="User rejected dangerous delete")
    assert len(gate.get_pending_actions()) == 0

    permitted_again = gate.evaluate_and_gate(action)
    assert permitted_again is False
    assert action.confirmation_status == ConfirmationStatus.REJECTED
