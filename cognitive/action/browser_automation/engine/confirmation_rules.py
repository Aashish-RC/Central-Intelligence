"""Confirmation Rules Gate: Intercepts consequential browser actions and enforces human approval."""

from typing import Dict, List, Optional
from ..core.interfaces import BaseActionClassifier, BaseConfirmationGate
from ..core.models import (
    ActionRiskLevel,
    BrowserAction,
    ConfirmationStatus,
)
from .action_classifier import ActionClassifier


class ConfirmationRulesGate(BaseConfirmationGate):
    """Guarantees that no consequential action executes without verified human approval."""

    def __init__(self, classifier: Optional[BaseActionClassifier] = None):
        self.classifier = classifier or ActionClassifier()
        self._pending_actions: Dict[str, BrowserAction] = {}
        self._action_decisions: Dict[str, ConfirmationStatus] = {}

    def evaluate_and_gate(
        self, action: BrowserAction, current_url: Optional[str] = None
    ) -> bool:
        # Classify the risk
        risk, reason = self.classifier.classify_action(action, current_url)
        action.risk_level = risk
        action.consequential_reason = reason

        if risk == ActionRiskLevel.CONSEQUENTIAL:
            # Check if this action was already pre-approved
            prior_status = self._action_decisions.get(action.action_id)
            if prior_status == ConfirmationStatus.APPROVED:
                action.confirmation_status = ConfirmationStatus.APPROVED
                return True
            elif prior_status == ConfirmationStatus.REJECTED:
                action.confirmation_status = ConfirmationStatus.REJECTED
                return False

            # Otherwise, hold for confirmation
            action.confirmation_status = ConfirmationStatus.PENDING_APPROVAL
            self._pending_actions[action.action_id] = action
            return False

        action.confirmation_status = ConfirmationStatus.NOT_REQUIRED
        return True

    def approve_action(self, action_id: str) -> None:
        action = self._pending_actions.pop(action_id, None)
        if action:
            action.confirmation_status = ConfirmationStatus.APPROVED
        self._action_decisions[action_id] = ConfirmationStatus.APPROVED

    def reject_action(self, action_id: str, reason: str = "User rejected action") -> None:
        action = self._pending_actions.pop(action_id, None)
        if action:
            action.confirmation_status = ConfirmationStatus.REJECTED
            action.consequential_reason = reason
        self._action_decisions[action_id] = ConfirmationStatus.REJECTED

    def get_pending_actions(self) -> List[BrowserAction]:
        return list(self._pending_actions.values())
