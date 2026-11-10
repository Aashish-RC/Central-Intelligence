"""Unit tests for SharingGate (Task 19.7)."""

import pytest
from surface.federation.review.sharing_gate import (
    SharingGate,
    PromotionScope,
    PromotionStatus,
)


@pytest.fixture
def gate():
    return SharingGate()


def test_agent_in_private_cannot_be_shared_with_team_without_review(gate: SharingGate):
    """Acceptance test: Agent in 'private' can't be shared with team without review."""
    agent_id = "agent_experimental_scraper"

    # Register agent in private scope
    gate.register_entity(agent_id, initial_scope=PromotionScope.PRIVATE)
    assert gate.get_scope(agent_id) == PromotionScope.PRIVATE

    # 1. Verify agent CANNOT be shared with team
    assert gate.can_share_with_scope(agent_id, PromotionScope.TEAM) is False
    assert gate.can_share_with_scope(agent_id, PromotionScope.ORG) is False

    # 2. Submit promotion request for team sharing
    req = gate.request_promotion(
        entity_id=agent_id,
        target_scope=PromotionScope.TEAM,
        submitter="dev_user_alice",
        code_or_manifest="def scrape(): ...",
    )
    assert req.status == PromotionStatus.PENDING_REVIEW

    # Still cannot share while review is pending
    assert gate.can_share_with_scope(agent_id, PromotionScope.TEAM) is False

    # 3. Reviewer approves promotion request
    approved_req = gate.review_and_decide(
        request_id=req.request_id,
        approved=True,
        reviewer="sec_officer_bob",
        notes="Security scan passed with zero secrets found.",
    )
    assert approved_req.status == PromotionStatus.APPROVED

    # 4. Now agent is promoted to team scope and can be shared with team
    assert gate.get_scope(agent_id) == PromotionScope.TEAM
    assert gate.can_share_with_scope(agent_id, PromotionScope.TEAM) is True

    # 5. But still CANNOT be shared with org without separate org-level review
    assert gate.can_share_with_scope(agent_id, PromotionScope.ORG) is False

