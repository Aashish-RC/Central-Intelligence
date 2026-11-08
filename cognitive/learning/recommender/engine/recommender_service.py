"""Pheonix Recommender Service: Evaluates candidates, arbitrates, and delivers decisions with transparent reasoning."""

from typing import Any, Dict, List, Optional
from ..core.interfaces import (
    BaseRecommenderService,
    BaseSecondOpinionArbiter,
    BaseTelemetryScorer,
)
from ..core.models import (
    CandidateScore,
    ModelCandidate,
    OptimizationGoal,
    RecommendationDecision,
    TaskProfile,
    TaskType,
    ToolCandidate,
    utc_now,
)
from .second_opinion import SecondOpinionArbiter
from .telemetry_scorer import TelemetryScorer


class RecommenderService(BaseRecommenderService):
    """Orchestrates model and tool recommendations with second-opinion arbitration."""

    def __init__(
        self,
        scorer: Optional[BaseTelemetryScorer] = None,
        arbiter: Optional[BaseSecondOpinionArbiter] = None,
    ):
        self.scorer = scorer or TelemetryScorer()
        self.arbiter = arbiter or SecondOpinionArbiter()

    def recommend_model(
        self, task: TaskProfile, candidates: List[ModelCandidate]
    ) -> RecommendationDecision:
        if not candidates:
            raise ValueError("No model candidates provided for recommendation")

        # Score all candidates
        scores: List[CandidateScore] = [
            self.scorer.score_model(c, task) for c in candidates
        ]
        # Sort descending by composite score
        scores.sort(key=lambda s: s.composite_score, reverse=True)

        top_score = scores[0]
        runner_up = scores[1] if len(scores) > 1 else None

        confidence_margin = (
            top_score.composite_score - runner_up.composite_score
            if runner_up
            else 1.0
        )

        chosen_id = top_score.candidate_id
        second_opinion_triggered = False
        second_opinion_notes = None

        if self.arbiter.should_trigger_second_opinion(top_score, runner_up, task):
            second_opinion_triggered = True
            if runner_up:
                chosen_id, second_opinion_notes = self.arbiter.arbitrate(
                    top_score, runner_up, task
                )
            else:
                second_opinion_notes = (
                    "Single candidate available; verified acceptable baseline."
                )

        one_line_reason = (
            f"Auto selected '{chosen_id}' (composite: {top_score.composite_score:.3f}, "
            f"cost: ${top_score.estimated_cost_usd:.4f}, latency: {top_score.estimated_latency_ms:.0f}ms): "
            f"optimal fit for {task.task_type.value} under {task.goal.value} policy"
        )

        return RecommendationDecision(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            recommended_id=chosen_id,
            candidate_type="model",
            composite_score=top_score.composite_score,
            runner_up_id=runner_up.candidate_id if runner_up else None,
            runner_up_score=runner_up.composite_score if runner_up else None,
            confidence_margin=round(confidence_margin, 4),
            one_line_reason=one_line_reason,
            second_opinion_triggered=second_opinion_triggered,
            second_opinion_notes=second_opinion_notes,
        )

    def recommend_tool(
        self, task: TaskProfile, candidates: List[ToolCandidate]
    ) -> RecommendationDecision:
        if not candidates:
            raise ValueError("No tool candidates provided for recommendation")

        scores: List[CandidateScore] = [
            self.scorer.score_tool(c, task) for c in candidates
        ]
        scores.sort(key=lambda s: s.composite_score, reverse=True)

        top_score = scores[0]
        runner_up = scores[1] if len(scores) > 1 else None

        confidence_margin = (
            top_score.composite_score - runner_up.composite_score
            if runner_up
            else 1.0
        )

        chosen_id = top_score.candidate_id
        second_opinion_triggered = False
        second_opinion_notes = None

        if self.arbiter.should_trigger_second_opinion(top_score, runner_up, task):
            second_opinion_triggered = True
            if runner_up:
                chosen_id, second_opinion_notes = self.arbiter.arbitrate(
                    top_score, runner_up, task
                )
            else:
                second_opinion_notes = (
                    "Single tool available; verified acceptable baseline."
                )

        one_line_reason = (
            f"Auto selected tool '{chosen_id}' (composite: {top_score.composite_score:.3f}, "
            f"overhead: ${top_score.estimated_cost_usd:.4f}): matched {task.task_type.value} requirements"
        )

        return RecommendationDecision(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            recommended_id=chosen_id,
            candidate_type="tool",
            composite_score=top_score.composite_score,
            runner_up_id=runner_up.candidate_id if runner_up else None,
            runner_up_score=runner_up.composite_score if runner_up else None,
            confidence_margin=round(confidence_margin, 4),
            one_line_reason=one_line_reason,
            second_opinion_triggered=second_opinion_triggered,
            second_opinion_notes=second_opinion_notes,
        )

    def compute_route_weights(
        self,
        candidates: List[ModelCandidate],
        task: Optional[TaskProfile] = None,
    ) -> Dict[str, float]:
        """
        Dynamically computes routing priority weights (0.0 to 1.0 scale)
        for model candidates based on empirical composite scores.
        """
        if not candidates:
            return {}

        task_profile = task or TaskProfile(
            task_id="dynamic_route_weights",
            task_type=TaskType.FAST_QUERY,
            goal=OptimizationGoal.BALANCED,
        )

        scores = [self.scorer.score_model(c, task_profile) for c in candidates]
        total_score = sum(max(0.01, s.composite_score) for s in scores)
        weights: Dict[str, float] = {}
        for s in scores:
            weights[s.candidate_id] = round(max(0.01, s.composite_score) / total_score, 4)
        return weights

    def export_gateway_route_weights(
        self,
        alias: str,
        candidates: List[ModelCandidate],
        task: Optional[TaskProfile] = None,
        gateway_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exports computed route weights formatted for the model-gateway router.
        Optionally synchronizes with a live model-gateway instance if gateway_url is provided.
        """
        weights = self.compute_route_weights(candidates, task)
        payload = {
            "alias": alias,
            "weights": weights,
            "updated_at": utc_now().isoformat(),
        }
        if gateway_url:
            try:
                import json
                import urllib.request
                req = urllib.request.Request(
                    f"{gateway_url.rstrip('/')}/v1/routes/{alias}/weights",
                    data=json.dumps({"weights": weights}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    payload["synced"] = resp.status == 200
            except Exception as e:
                payload["sync_error"] = str(e)
                payload["synced"] = False
        return payload
