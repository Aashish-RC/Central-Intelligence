"""Platform Release Gates tied to L11 Evaluation (L17 Release - Task 17.12).

Wires L11 quality metrics and release gates into the production release pipeline.
Blocks deployment rollouts if evaluation metrics (accuracy, pass rate, hallucination rate)
regress by more than acceptable thresholds (e.g. 10% quality drop).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from control.evaluation.experiments.release_gates import (
    QualityGatePolicy,
    ReleaseGateEvaluator,
    ReleaseGateResult,
)

logger = logging.getLogger(__name__)


class GateStatus(str, Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"


@dataclass
class GateDecision:
    """Decision emitted by the quality release gate."""
    release_id: str
    status: GateStatus
    passed: bool
    reasons: List[str]
    candidate_metrics: Dict[str, Any]
    baseline_metrics: Optional[Dict[str, Any]] = None
    evaluated_at: float = field(default_factory=time.time)


class PlatformReleaseGate:
    """Release gate orchestrator evaluating release candidates against L11 quality benchmarks."""

    def __init__(
        self,
        max_allowed_regression: float = 0.05,
        min_pass_rate: float = 0.85,
        max_hallucination_rate: float = 0.05,
        min_sample_size: int = 10,
    ) -> None:
        self.policy = QualityGatePolicy(
            min_pass_rate=min_pass_rate,
            max_accuracy_regression=max_allowed_regression,
            max_hallucination_rate=max_hallucination_rate,
            min_sample_size=min_sample_size,
        )
        self.evaluator = ReleaseGateEvaluator(policy=self.policy)
        self._history: List[GateDecision] = []

    def evaluate_release(
        self,
        release_id: str,
        candidate_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]] = None,
    ) -> GateDecision:
        """Evaluate candidate release metrics against baseline using L11 evaluation policy."""
        result: ReleaseGateResult = self.evaluator.evaluate(
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
        )

        status = GateStatus.APPROVED if result.passed else GateStatus.BLOCKED
        decision = GateDecision(
            release_id=release_id,
            status=status,
            passed=result.passed,
            reasons=result.reasons,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
        )

        self._history.append(decision)
        if not result.passed:
            logger.warning(
                "Release gate BLOCKED rollout '%s': %s",
                release_id,
                "; ".join(result.reasons),
            )
        else:
            logger.info("Release gate APPROVED rollout '%s'", release_id)

        return decision

    def get_history(self) -> List[GateDecision]:
        return list(self._history)
