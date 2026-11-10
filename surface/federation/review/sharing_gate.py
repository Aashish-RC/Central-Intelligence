"""Review-Before-Wider-Sharing Gate (L19 Federation - Task 19.35).

Enforces mandatory security and governance reviews before agents, workflows,
or domain capabilities can be promoted from Private -> Team -> Org.
Extends the L5 sharing pipeline.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from cognitive.action.safety.sharing_pipeline import (
    ReviewSharingPipeline,
    SharingScope,
    SharingStatus,
)

logger = logging.getLogger(__name__)


class PromotionScope(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    ORG = "org"


class PromotionStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PromotionRequest:
    """A proposal to promote an agent/workflow to a wider visibility scope."""
    request_id: str
    entity_id: str  # agent_id or workflow_id
    entity_type: str  # "agent", "workflow", "tool"
    current_scope: PromotionScope
    target_scope: PromotionScope
    submitter: str
    status: PromotionStatus = PromotionStatus.PENDING_REVIEW
    reviewer: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    reviewed_at: Optional[float] = None
    decision_notes: Optional[str] = None


class SharingGate:
    """Gatekeeper ensuring assets cannot be shared across team or org boundaries without review."""

    def __init__(self, pipeline: Optional[ReviewSharingPipeline] = None) -> None:
        self.pipeline = pipeline or ReviewSharingPipeline(auto_approve_clean_team_internal=False)
        # entity_id -> current PromotionScope
        self._entity_scopes: Dict[str, PromotionScope] = {}
        # request_id -> PromotionRequest
        self._requests: Dict[str, PromotionRequest] = {}

    def register_entity(
        self,
        entity_id: str,
        initial_scope: PromotionScope = PromotionScope.PRIVATE,
    ) -> None:
        """Register agent or workflow under governance."""
        self._entity_scopes[entity_id] = initial_scope

    def get_scope(self, entity_id: str) -> PromotionScope:
        """Get active scope of agent (defaults to PRIVATE)."""
        return self._entity_scopes.get(entity_id, PromotionScope.PRIVATE)

    def can_share_with_scope(self, entity_id: str, target_scope: PromotionScope) -> bool:
        """Check if entity is authorized to operate in target scope without pending review."""
        current = self.get_scope(entity_id)

        scope_levels = {
            PromotionScope.PRIVATE: 1,
            PromotionScope.TEAM: 2,
            PromotionScope.ORG: 3,
        }

        # If current level is already equal to or higher than target, sharing is permitted
        return scope_levels[current] >= scope_levels[target_scope]

    def request_promotion(
        self,
        entity_id: str,
        target_scope: PromotionScope,
        submitter: str,
        code_or_manifest: str = "",
    ) -> PromotionRequest:
        """Request promotion from current scope to a wider scope."""
        current = self.get_scope(entity_id)
        if current == target_scope:
            req_id = f"req_{uuid.uuid4().hex[:8]}"
            req = PromotionRequest(
                request_id=req_id,
                entity_id=entity_id,
                entity_type="agent",
                current_scope=current,
                target_scope=target_scope,
                submitter=submitter,
                status=PromotionStatus.APPROVED,
                decision_notes="Already at requested scope",
            )
            return req

        req_id = f"req_{uuid.uuid4().hex[:8]}"
        req = PromotionRequest(
            request_id=req_id,
            entity_id=entity_id,
            entity_type="agent",
            current_scope=current,
            target_scope=target_scope,
            submitter=submitter,
            status=PromotionStatus.PENDING_REVIEW,
        )
        self._requests[req_id] = req
        logger.info(
            "Promotion requested for '%s': %s -> %s by %s",
            entity_id,
            current.value,
            target_scope.value,
            submitter,
        )
        return req

    def review_and_decide(
        self,
        request_id: str,
        approved: bool,
        reviewer: str,
        notes: Optional[str] = None,
    ) -> PromotionRequest:
        """Review gate: Approve or reject promotion request."""
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Promotion request not found: {request_id}")

        req.status = PromotionStatus.APPROVED if approved else PromotionStatus.REJECTED
        req.reviewer = reviewer
        req.decision_notes = notes
        req.reviewed_at = time.time()

        if approved:
            # Advance entity's scope
            self._entity_scopes[req.entity_id] = req.target_scope
            logger.info("Entity '%s' promoted to scope '%s'", req.entity_id, req.target_scope.value)
        else:
            logger.warning("Promotion of '%s' to '%s' REJECTED: %s", req.entity_id, req.target_scope.value, notes)

        return req
