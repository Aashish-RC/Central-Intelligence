"""Specialized Brain Factory (L19 Federation - Tasks 19.01-19.07).

Instantiates domain-specialized cognitive brains (e.g. Legal, Software Engineering,
Healthcare, Finance) from the core base brain with customized tuning, domain corpora,
personas, and compliance modes. Manages lifecycle from health monitoring to retirement.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BrainLifecycleStatus(str, Enum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    DEGRADED = "degraded"
    RETIRED = "retired"


@dataclass
class SpecializedBrain:
    """An autonomous specialized cognitive brain."""
    brain_id: str
    name: str
    domain: str
    persona: str
    domain_corpus: List[str] = field(default_factory=list)
    compliance_mode: bool = True
    status: BrainLifecycleStatus = BrainLifecycleStatus.ACTIVE
    health_score: float = 1.0  # 0.0 to 1.0
    created_at: float = field(default_factory=time.time)
    retired_at: Optional[float] = None
    archived_learnings: List[Dict[str, Any]] = field(default_factory=list)
    public_key: str = field(default_factory=lambda: f"pk_{uuid.uuid4().hex[:16]}")


class SpecializedBrainFactory:
    """Factory creating and managing domain-specialized cognitive brains."""

    def __init__(self, base_brain_model: str = "claude-3-7-sonnet") -> None:
        self.base_brain_model = base_brain_model
        self._brains: Dict[str, SpecializedBrain] = {}

    def create_brain(
        self,
        domain: str,
        name: str,
        persona: str,
        corpus: Optional[List[str]] = None,
        compliance_mode: bool = True,
    ) -> SpecializedBrain:
        """Create a new domain-specialized brain."""
        brain_id = f"brain_{domain.lower()}_{uuid.uuid4().hex[:6]}"
        brain = SpecializedBrain(
            brain_id=brain_id,
            name=name,
            domain=domain,
            persona=persona,
            domain_corpus=list(corpus or []),
            compliance_mode=compliance_mode,
            status=BrainLifecycleStatus.ACTIVE,
            health_score=1.0,
        )
        self._brains[brain_id] = brain
        logger.info(
            "Created specialized brain '%s' (domain: %s, compliance_mode: %s)",
            name,
            domain,
            compliance_mode,
        )
        return brain

    def monitor_brain_health(self, brain_id: str, error_rate: float = 0.0) -> float:
        """Evaluate operational health score of specialized brain."""
        brain = self._brains.get(brain_id)
        if not brain:
            raise ValueError(f"Brain not found: {brain_id}")

        score = max(0.0, min(1.0, 1.0 - error_rate))
        brain.health_score = score
        if score < 0.7:
            brain.status = BrainLifecycleStatus.DEGRADED
        elif brain.status == BrainLifecycleStatus.DEGRADED and score >= 0.7:
            brain.status = BrainLifecycleStatus.ACTIVE
        return brain.health_score

    def retire_brain(self, brain_id: str, learnings_summary: str) -> SpecializedBrain:
        """Retire specialized brain and archive its accumulated domain learnings."""
        brain = self._brains.get(brain_id)
        if not brain:
            raise ValueError(f"Brain not found: {brain_id}")

        brain.status = BrainLifecycleStatus.RETIRED
        brain.retired_at = time.time()
        archive_record = {
            "retired_at": brain.retired_at,
            "summary": learnings_summary,
            "domain": brain.domain,
            "final_health": brain.health_score,
        }
        brain.archived_learnings.append(archive_record)
        logger.info("Retired specialized brain %s with archived learnings.", brain_id)
        return brain

    def get_brain(self, brain_id: str) -> Optional[SpecializedBrain]:
        return self._brains.get(brain_id)

    def list_active_brains(self) -> List[SpecializedBrain]:
        return [b for b in self._brains.values() if b.status != BrainLifecycleStatus.RETIRED]
