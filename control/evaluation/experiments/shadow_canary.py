"""Shadow Traffic & Canary Deployment Evaluation (Layer 11: Evaluation & Quality, Features 11.22, 11.23)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("control.evaluation.shadow_canary")


@dataclass
class ShadowEvaluationComparison:
    """Pairwise comparison between live production response and shadow candidate."""
    trace_id: str
    production_response: str
    shadow_response: str
    production_score: float
    shadow_score: float
    shadow_latency_ms: float
    shadow_error: Optional[str] = None


@dataclass
class CanaryHealthReport:
    """Canary health status and automated rollback trigger."""
    canary_percentage: float
    total_canary_requests: int
    error_count: int
    error_rate: float
    mean_quality_score: float
    baseline_quality_score: float
    should_rollback: bool
    reason: str


class ShadowTrafficEvaluator:
    """Evaluates shadow traffic asynchronously alongside production traffic without user impact."""

    def __init__(self):
        self._comparisons: List[ShadowEvaluationComparison] = []

    def record_shadow_run(
        self,
        trace_id: str,
        prod_resp: str,
        shadow_resp: str,
        prod_score: float,
        shadow_score: float,
        shadow_latency_ms: float,
        error: Optional[str] = None,
    ) -> ShadowEvaluationComparison:
        comp = ShadowEvaluationComparison(
            trace_id=trace_id,
            production_response=prod_resp,
            shadow_response=shadow_resp,
            production_score=prod_score,
            shadow_score=shadow_score,
            shadow_latency_ms=shadow_latency_ms,
            shadow_error=error,
        )
        self._comparisons.append(comp)
        return comp

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        if not self._comparisons:
            return {"total": 0, "mean_prod_score": 0.0, "mean_shadow_score": 0.0}

        prod_scores = [c.production_score for c in self._comparisons]
        shad_scores = [c.shadow_score for c in self._comparisons]

        return {
            "total": len(self._comparisons),
            "mean_prod_score": round(sum(prod_scores) / len(prod_scores), 4),
            "mean_shadow_score": round(sum(shad_scores) / len(shad_scores), 4),
            "shadow_parity": round(
                (sum(shad_scores) / max(1e-6, sum(prod_scores))), 4
            ),
        }


class CanaryEvaluator:
    """Evaluates canary release progression and flags regression for rollback."""

    def __init__(
        self,
        canary_percentage: float = 0.05,
        max_error_rate: float = 0.02,
        max_score_drop: float = 0.05,
    ):
        self.canary_percentage = canary_percentage
        self.max_error_rate = max_error_rate
        self.max_score_drop = max_score_drop
        self._scores: List[float] = []
        self._errors: int = 0

    def record_canary_request(self, score: float, is_error: bool = False) -> None:
        self._scores.append(score)
        if is_error:
            self._errors += 1

    def evaluate_health(self, baseline_quality_score: float = 0.85) -> CanaryHealthReport:
        total = len(self._scores)
        if total == 0:
            return CanaryHealthReport(
                canary_percentage=self.canary_percentage,
                total_canary_requests=0,
                error_count=0,
                error_rate=0.0,
                mean_quality_score=baseline_quality_score,
                baseline_quality_score=baseline_quality_score,
                should_rollback=False,
                reason="No canary requests received",
            )

        err_rate = self._errors / total
        mean_score = sum(self._scores) / total

        should_rollback = False
        reasons = []

        if err_rate > self.max_error_rate:
            should_rollback = True
            reasons.append(f"Error rate {err_rate:.2%} exceeded max {self.max_error_rate:.2%}")

        if (baseline_quality_score - mean_score) > self.max_score_drop:
            should_rollback = True
            reasons.append(
                f"Quality score dropped from {baseline_quality_score:.2f} to {mean_score:.2f} "
                f"(exceeded {self.max_score_drop:.2f} drop threshold)"
            )

        return CanaryHealthReport(
            canary_percentage=self.canary_percentage,
            total_canary_requests=total,
            error_count=self._errors,
            error_rate=round(err_rate, 4),
            mean_quality_score=round(mean_score, 4),
            baseline_quality_score=baseline_quality_score,
            should_rollback=should_rollback,
            reason="; ".join(reasons) if reasons else "Canary is healthy and meeting quality targets",
        )

