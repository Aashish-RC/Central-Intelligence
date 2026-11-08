"""Second-Opinion Rule Arbiter: Triggers double-check or consensus when confidence is marginal or task risk is elevated."""

from typing import Optional, Tuple
from ..core.interfaces import BaseSecondOpinionArbiter
from ..core.models import (
    CandidateScore,
    RiskLevel,
    TaskProfile,
)


class SecondOpinionArbiter(BaseSecondOpinionArbiter):
    """Evaluates candidate confidence deltas and arbitrates high-risk or narrow-margin choices."""

    def __init__(self, confidence_threshold: float = 0.05):
        self.confidence_threshold = confidence_threshold

    def should_trigger_second_opinion(
        self,
        top_score: CandidateScore,
        runner_up: Optional[CandidateScore],
        task: TaskProfile,
    ) -> bool:
        # High or Critical risk tasks always trigger second opinion
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True

        # If there is no runner-up, no arbitration needed
        if not runner_up:
            return False

        # Narrow margin trigger: score difference is within confidence threshold
        score_diff = abs(top_score.composite_score - runner_up.composite_score)
        if score_diff <= self.confidence_threshold:
            return True

        # Low reliability trigger on top score
        if top_score.reliability_score < 0.90:
            return True

        return False

    def arbitrate(
        self,
        top_candidate: CandidateScore,
        runner_up: CandidateScore,
        task: TaskProfile,
    ) -> Tuple[str, str]:
        """Arbitrates between top two candidates and outputs choice with justification."""
        # For High/Critical risk tasks, prioritize higher reliability and quality over cost/latency
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if runner_up.reliability_score > top_candidate.reliability_score + 0.05:
                reason = (
                    f"Second-opinion arbitration: Switched to '{runner_up.candidate_id}' due to superior "
                    f"reliability ({runner_up.reliability_score:.2f} vs {top_candidate.reliability_score:.2f}) "
                    f"for {task.risk_level.value} risk task."
                )
                return runner_up.candidate_id, reason
            elif runner_up.quality_score > top_candidate.quality_score + 0.05:
                reason = (
                    f"Second-opinion arbitration: Switched to '{runner_up.candidate_id}' due to superior "
                    f"quality score ({runner_up.quality_score:.2f} vs {top_candidate.quality_score:.2f}) "
                    f"for {task.risk_level.value} risk task."
                )
                return runner_up.candidate_id, reason

        # For tight margins, check if runner-up provides significantly lower latency or cost
        score_diff = abs(top_candidate.composite_score - runner_up.composite_score)
        if score_diff <= self.confidence_threshold:
            if (
                runner_up.estimated_latency_ms
                < top_candidate.estimated_latency_ms * 0.6
            ):
                reason = (
                    f"Second-opinion arbitration: Selected '{runner_up.candidate_id}' offering 40%+ "
                    f"faster latency ({runner_up.estimated_latency_ms}ms vs {top_candidate.estimated_latency_ms}ms) "
                    f"within marginal score delta ({score_diff:.3f})."
                )
                return runner_up.candidate_id, reason

        # Confirm top candidate with verified second-opinion endorsement
        reason = (
            f"Second-opinion consensus confirmed '{top_candidate.candidate_id}' with composite score "
            f"{top_candidate.composite_score:.3f} and lead margin {score_diff:.3f}."
        )
        return top_candidate.candidate_id, reason
