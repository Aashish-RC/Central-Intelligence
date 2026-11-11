"""Canary Deployment Controller (L17 Release - Feature 17.04).

Orchestrates percentage-based canary rollouts backed by GrowthBookAdapter
feature flags and L11 PlatformReleaseGate quality evaluations, automatically
rolling back traffic to 0% when candidate metrics regress.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from platform_infra.release.flags.growthbook_adapter import FeatureFlag, GrowthBookAdapter
from platform_infra.release.gates.release_gate import GateStatus, PlatformReleaseGate

logger = logging.getLogger(__name__)


class CanaryState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CanaryRollout:
    """Tracked state of an in-flight canary deployment."""

    release_id: str
    flag_key: str
    percentage: float
    baseline_metrics: Dict[str, Any]
    state: CanaryState = CanaryState.ACTIVE
    history: List[str] = field(default_factory=list)


@dataclass
class CanaryStepResult:
    """Result of advancing or rolling back a canary rollout step."""

    release_id: str
    state: CanaryState
    percentage: float
    gate_status: GateStatus
    reasons: List[str] = field(default_factory=list)


class CanaryDeploymentManager:
    """Wires GrowthBook traffic splitting with L11 PlatformReleaseGate checks."""

    def __init__(
        self,
        flag_adapter: Optional[GrowthBookAdapter] = None,
        release_gate: Optional[PlatformReleaseGate] = None,
    ) -> None:
        self.flag_adapter = flag_adapter or GrowthBookAdapter(client_key="dev-canary")
        self.release_gate = release_gate or PlatformReleaseGate()
        self._rollouts: Dict[str, CanaryRollout] = {}

    def start_canary(
        self,
        release_id: str,
        flag_key: str,
        initial_percentage: float = 5.0,
        baseline_metrics: Optional[Dict[str, Any]] = None,
    ) -> CanaryRollout:
        """Start a canary rollout at initial_percentage (default 5%) via GrowthBook."""
        pct = max(0.0, min(100.0, float(initial_percentage)))
        self.flag_adapter.register_flag(
            FeatureFlag(
                key=flag_key,
                enabled=True,
                rollout_percentage=pct,
                value=release_id,
                fallback_value="baseline",
            )
        )
        rollout = CanaryRollout(
            release_id=release_id,
            flag_key=flag_key,
            percentage=pct,
            baseline_metrics=dict(baseline_metrics or {}),
            state=CanaryState.ACTIVE,
            history=[f"started at {pct}%"],
        )
        self._rollouts[release_id] = rollout
        return rollout

    def advance_canary(
        self,
        release_id: str,
        candidate_metrics: Dict[str, Any],
        target_percentage: float = 100.0,
    ) -> CanaryStepResult:
        """Evaluate candidate metrics via PlatformReleaseGate; expand or auto-rollback."""
        rollout = self._rollouts[release_id]
        decision = self.release_gate.evaluate_release(
            release_id=release_id,
            candidate_metrics=candidate_metrics,
            baseline_metrics=rollout.baseline_metrics or None,
        )

        if not decision.passed:
            # Auto-rollback traffic and disable flag
            self.flag_adapter.set_rollout_percentage(rollout.flag_key, 0.0)
            self.flag_adapter.toggle_flag(rollout.flag_key, False)
            rollout.percentage = 0.0
            rollout.state = CanaryState.ROLLED_BACK
            rollout.history.append(f"rolled back: {'; '.join(decision.reasons)}")
            logger.warning("Canary '%s' auto-rolled back: %s", release_id, decision.reasons)
            return CanaryStepResult(
                release_id=release_id,
                state=CanaryState.ROLLED_BACK,
                percentage=0.0,
                gate_status=decision.status,
                reasons=list(decision.reasons),
            )

        next_pct = max(0.0, min(100.0, float(target_percentage)))
        self.flag_adapter.set_rollout_percentage(rollout.flag_key, next_pct)
        rollout.percentage = next_pct
        rollout.state = CanaryState.COMPLETED if next_pct >= 100.0 else CanaryState.ACTIVE
        rollout.history.append(f"expanded to {next_pct}%")
        return CanaryStepResult(
            release_id=release_id,
            state=rollout.state,
            percentage=next_pct,
            gate_status=decision.status,
            reasons=list(decision.reasons),
        )

    def evaluate_user(self, release_id: str, user_id: str) -> bool:
        """Check whether a user lands in the canary bucket."""
        rollout = self._rollouts[release_id]
        return self.flag_adapter.is_on(rollout.flag_key, user_id)

    def get_rollout(self, release_id: str) -> CanaryRollout:
        return self._rollouts[release_id]

