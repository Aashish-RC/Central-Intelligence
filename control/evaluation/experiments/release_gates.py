"""Automated Quality Release Gates (Layer 11: Evaluation & Quality, Feature 11.24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QualityGatePolicy:
    """Configurable thresholds that a candidate model or prompt must satisfy to pass release gate."""
    min_pass_rate: float = 0.90
    max_accuracy_regression: float = 0.02  # Maximum allowed drop in composite score
    max_hallucination_rate: float = 0.05
    min_sample_size: int = 20


@dataclass
class ReleaseGateResult:
    """Decision from evaluating candidate against release gate policy."""
    passed: bool
    reasons: List[str]
    candidate_metrics: Dict[str, Any]
    baseline_metrics: Optional[Dict[str, Any]] = None


class ReleaseGateEvaluator:
    """Blocks candidate model, prompt, or agent deployment on quality regression."""

    def __init__(self, policy: Optional[QualityGatePolicy] = None):
        self.policy = policy or QualityGatePolicy()

    def evaluate(
        self,
        candidate_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]] = None,
    ) -> ReleaseGateResult:
        reasons: List[str] = []

        sample_size = candidate_metrics.get("sample_size", 0)
        if sample_size < self.policy.min_sample_size:
            reasons.append(
                f"Sample size {sample_size} is below required minimum of {self.policy.min_sample_size}"
            )

        pass_rate = candidate_metrics.get("pass_rate", 0.0)
        if pass_rate < self.policy.min_pass_rate:
            reasons.append(
                f"Pass rate {pass_rate:.2%} is below minimum bar {self.policy.min_pass_rate:.2%}"
            )

        hallucination_rate = candidate_metrics.get("hallucination_rate", 0.0)
        if hallucination_rate > self.policy.max_hallucination_rate:
            reasons.append(
                f"Hallucination rate {hallucination_rate:.2%} exceeds maximum allowed {self.policy.max_hallucination_rate:.2%}"
            )

        if baseline_metrics:
            base_score = baseline_metrics.get("accuracy_score", 0.0)
            cand_score = candidate_metrics.get("accuracy_score", 0.0)
            drop = base_score - cand_score
            if drop > self.policy.max_accuracy_regression:
                reasons.append(
                    f"Accuracy regression of {drop:.4f} exceeds allowable delta of {self.policy.max_accuracy_regression:.4f} "
                    f"(Baseline: {base_score:.4f}, Candidate: {cand_score:.4f})"
                )

        passed = len(reasons) == 0
        return ReleaseGateResult(
            passed=passed,
            reasons=reasons,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
        )
