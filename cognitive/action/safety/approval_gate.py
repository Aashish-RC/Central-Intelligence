"""Approval Gate: Human-in-the-loop pause and signoff manager for High/Critical actions.

Feature: 5.23
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from .models import ActionRiskAssessment, ApprovalGateRequest, RiskLevel


class ApprovalGate:
    """Manages pending approval requests, pausing actions that exceed risk tolerance."""

    def __init__(self):
        self._pending_requests: Dict[str, ApprovalGateRequest] = {}
        self._history: List[ApprovalGateRequest] = []

    def request_approval(
        self,
        assessment: ActionRiskAssessment,
        agent_id: str,
    ) -> ApprovalGateRequest:
        """Creates an approval request for an action requiring signoff."""
        req = ApprovalGateRequest(
            assessment=assessment,
            agent_id=agent_id,
            status="pending",
        )
        self._pending_requests[req.gate_id] = req
        return req

    def resolve(
        self,
        gate_id: str,
        approved: bool,
        approver: str,
        decision_reason: Optional[str] = None,
    ) -> ApprovalGateRequest:
        """Resolves a pending request with an approval or rejection."""
        req = self._pending_requests.pop(gate_id, None)
        if not req:
            raise KeyError(f"Approval gate request '{gate_id}' not found or already resolved.")

        req.status = "approved" if approved else "rejected"
        req.approver = approver
        req.decision_reason = decision_reason or ("Approved by supervisor" if approved else "Rejected")
        req.resolved_at = datetime.now(timezone.utc)

        self._history.append(req)
        return req

    def get_pending(self) -> List[ApprovalGateRequest]:
        """Returns all open approval requests awaiting decision."""
        return list(self._pending_requests.values())

    def get_history(self) -> List[ApprovalGateRequest]:
        """Returns history of resolved approval requests."""
        return list(self._history)
