"""Telemetry-driven empirical performance scorer."""

from typing import Dict, Optional
from ..core.interfaces import BaseTelemetryScorer
from ..core.models import (
    CandidateMetrics,
    CandidateScore,
    ModelCandidate,
    OptimizationGoal,
    ScoringWeights,
    TaskProfile,
    ToolCandidate,
)


class TelemetryScorer(BaseTelemetryScorer):
    """Empirically scores models and tools based on live telemetry, cost, latency, and task fit."""

    def __init__(self, ema_alpha: float = 0.2):
        self.ema_alpha = ema_alpha
        # Dynamic in-memory telemetry table: candidate_id -> CandidateMetrics
        self._telemetry: Dict[str, CandidateMetrics] = {}

    def record_execution(
        self,
        candidate_id: str,
        latency_ms: float,
        cost_usd: float,
        success: bool,
        quality_rating: Optional[float] = None,
    ) -> None:
        metrics = self._telemetry.get(candidate_id)
        if not metrics:
            metrics = CandidateMetrics(
                total_invocations=1,
                successful_invocations=1 if success else 0,
                avg_latency_ms=latency_ms,
                p95_latency_ms=latency_ms * 1.2,
                avg_cost_per_1k_tokens=cost_usd,
                quality_score=quality_rating if quality_rating is not None else 0.85,
            )
            self._telemetry[candidate_id] = metrics
            return

        # Update running stats using Exponential Moving Average
        metrics.total_invocations += 1
        if success:
            metrics.successful_invocations += 1

        metrics.avg_latency_ms = (
            self.ema_alpha * latency_ms + (1 - self.ema_alpha) * metrics.avg_latency_ms
        )
        if latency_ms > metrics.p95_latency_ms:
            metrics.p95_latency_ms = latency_ms

        if quality_rating is not None:
            metrics.quality_score = (
                self.ema_alpha * quality_rating
                + (1 - self.ema_alpha) * metrics.quality_score
            )

    def _get_weights_for_goal(self, goal: OptimizationGoal) -> ScoringWeights:
        if goal == OptimizationGoal.MIN_COST:
            return ScoringWeights(
                cost_weight=0.60,
                latency_weight=0.15,
                quality_weight=0.15,
                reliability_weight=0.10,
            )
        elif goal == OptimizationGoal.MIN_LATENCY:
            return ScoringWeights(
                cost_weight=0.10,
                latency_weight=0.60,
                quality_weight=0.15,
                reliability_weight=0.15,
            )
        elif goal == OptimizationGoal.MAX_QUALITY:
            return ScoringWeights(
                cost_weight=0.10,
                latency_weight=0.10,
                quality_weight=0.55,
                reliability_weight=0.25,
            )
        else:  # BALANCED
            return ScoringWeights(
                cost_weight=0.25,
                latency_weight=0.25,
                quality_weight=0.30,
                reliability_weight=0.20,
            )

    def score_model(
        self, candidate: ModelCandidate, task: TaskProfile
    ) -> CandidateScore:
        # Check if we have live historical metrics, otherwise fall back to candidate defaults
        metrics = self._telemetry.get(candidate.candidate_id, candidate.metrics)

        # Estimate task cost
        input_cost = (task.prompt_token_estimate / 1000.0) * candidate.cost_per_1k_input
        output_cost = (
            task.expected_output_tokens / 1000.0
        ) * candidate.cost_per_1k_output
        estimated_cost = input_cost + output_cost

        # Calculate normalized sub-scores (0.0 to 1.0, higher is better)
        # Cost reference normalization: Assume $0.05 is upper reference
        cost_score = max(0.0, min(1.0, 1.0 - (estimated_cost / 0.05)))

        # Latency reference normalization: Assume 2500ms is max acceptable latency
        est_latency = metrics.avg_latency_ms
        latency_score = max(0.0, min(1.0, 1.0 - (est_latency / 2500.0)))

        # Reliability score from empirical success rate
        reliability_score = metrics.success_rate

        # Quality score based on model base quality + required capability match
        capability_match = 1.0
        if task.required_capabilities:
            matched = sum(
                1 for cap in task.required_capabilities if cap in candidate.capabilities
            )
            capability_match = matched / len(task.required_capabilities)

        quality_score = max(
            0.0, min(1.0, metrics.quality_score * 0.7 + capability_match * 0.3)
        )

        weights = self._get_weights_for_goal(task.goal)
        composite = (
            weights.cost_weight * cost_score
            + weights.latency_weight * latency_score
            + weights.quality_weight * quality_score
            + weights.reliability_weight * reliability_score
        )

        return CandidateScore(
            candidate_id=candidate.candidate_id,
            cost_score=round(cost_score, 4),
            latency_score=round(latency_score, 4),
            quality_score=round(quality_score, 4),
            reliability_score=round(reliability_score, 4),
            composite_score=round(composite, 4),
            estimated_cost_usd=round(estimated_cost, 6),
            estimated_latency_ms=round(est_latency, 2),
        )

    def score_tool(
        self, candidate: ToolCandidate, task: TaskProfile
    ) -> CandidateScore:
        # Tool cost is estimated from token overhead
        est_cost = (candidate.token_overhead / 1000.0) * 0.001
        cost_score = max(0.0, min(1.0, 1.0 - (est_cost / 0.01)))

        latency_score = max(0.0, min(1.0, 1.0 - (candidate.avg_latency_ms / 1000.0)))
        reliability_score = max(0.0, 1.0 - candidate.error_rate)

        cap_score = 1.0
        if task.required_capabilities:
            matched = sum(
                1 for cap in task.required_capabilities if cap in candidate.capabilities
            )
            cap_score = matched / len(task.required_capabilities)

        weights = self._get_weights_for_goal(task.goal)
        composite = (
            weights.cost_weight * cost_score
            + weights.latency_weight * latency_score
            + weights.quality_weight * cap_score
            + weights.reliability_weight * reliability_score
        )

        return CandidateScore(
            candidate_id=candidate.tool_id,
            cost_score=round(cost_score, 4),
            latency_score=round(latency_score, 4),
            quality_score=round(cap_score, 4),
            reliability_score=round(reliability_score, 4),
            composite_score=round(composite, 4),
            estimated_cost_usd=round(est_cost, 6),
            estimated_latency_ms=round(candidate.avg_latency_ms, 2),
        )
