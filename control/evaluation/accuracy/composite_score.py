"""🚩 Crown Jewel: Accuracy Score Evaluator (Layer 11: Evaluation & Quality, Feature 11.14).

Computes 3-pillar composite accuracy score:
    S_composite = w1 * S_feedback + w2 * S_web + w3 * S_consensus

Thresholds:
    S >= 0.80 -> deliver directly
    0.50 <= S < 0.80 -> flag low-confidence
    S < 0.50 -> trigger second opinion (Unblocks DEF-03)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .calibration import ConfidenceCalibrator
from .consensus_pillar import CandidatePrediction, ConsensusPillar
from .feedback_pillar import FeedbackPillar
from .thresholds import AccuracyThresholdConfig, ThresholdAction
from .web_pillar import WebPillar

logger = logging.getLogger("control.evaluation.accuracy")


@dataclass
class AccuracyScore:
    """Structured multi-pillar accuracy score evaluation."""
    composite: float
    feedback: float
    web: float
    consensus: float
    threshold_action: ThresholdAction
    weights: Tuple[float, float, float]
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    explanation: str = ""
    claims_evaluated: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "composite": self.composite,
            "feedback": self.feedback,
            "web": self.web,
            "consensus": self.consensus,
            "threshold_action": self.threshold_action.value,
            "weights": list(self.weights),
            "task_id": self.task_id,
            "user_id": self.user_id,
            "explanation": self.explanation,
            "claims_evaluated": self.claims_evaluated,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class AccuracyScoreEvaluator:
    """Evaluates candidate responses across the 3 pillars of truth: user feedback, web facts, model consensus."""

    def __init__(
        self,
        weights: Tuple[float, float, float] = (0.3, 0.4, 0.3),
        threshold_config: Optional[AccuracyThresholdConfig] = None,
        feedback_pillar: Optional[FeedbackPillar] = None,
        web_pillar: Optional[WebPillar] = None,
        consensus_pillar: Optional[ConsensusPillar] = None,
    ):
        # Normalize weights
        total_w = sum(weights) or 1.0
        self.weights = (weights[0] / total_w, weights[1] / total_w, weights[2] / total_w)
        self.thresholds = threshold_config or AccuracyThresholdConfig()
        self.feedback_pillar = feedback_pillar or FeedbackPillar()
        self.web_pillar = web_pillar or WebPillar()
        self.consensus_pillar = consensus_pillar or ConsensusPillar()
        self.calibrator = ConfidenceCalibrator()

    def evaluate_response(
        self,
        response_text: str,
        user_id: Optional[str] = None,
        task_id: Optional[str] = None,
        reference_knowledge: Optional[List[str]] = None,
        candidate_predictions: Optional[List[str]] = None,
        explicit_feedback_score: Optional[float] = None,
        stated_confidence: Optional[float] = None,
    ) -> AccuracyScore:
        """Calculates full 3-pillar composite accuracy score and recommended threshold action."""

        # Pillar 1: S_feedback
        if explicit_feedback_score is not None:
            s_feedback = max(0.0, min(1.0, explicit_feedback_score))
        else:
            s_feedback = self.feedback_pillar.get_feedback_score(user_id=user_id, task_id=task_id)

        # Pillar 2: S_web
        claims = self.web_pillar.decompose_claims(response_text)
        s_web = self.web_pillar.calculate_web_score(claims, reference_knowledge=reference_knowledge)

        # Pillar 3: S_consensus
        if candidate_predictions and len(candidate_predictions) >= 2:
            s_consensus = self.consensus_pillar.calculate_direct_consensus(candidate_predictions)
        elif task_id and self.consensus_pillar.has_consensus_data(task_id):
            s_consensus = self.consensus_pillar.agreement_score(task_id)
        else:
            s_consensus = 0.50  # Neutral prior when single candidate without consensus

        # Composite score
        w1, w2, w3 = self.weights
        s_composite = round((w1 * s_feedback) + (w2 * s_web) + (w3 * s_consensus), 4)

        # Action from threshold
        action = self.thresholds.evaluate_action(s_composite)

        # Track calibration if stated confidence provided
        if stated_confidence is not None:
            self.calibrator.record_prediction(
                stated_confidence=stated_confidence,
                actual_outcome=(s_composite >= self.thresholds.second_opinion_threshold),
            )

        explanation = (
            f"Composite Score: {s_composite:.2f} (Feedback: {s_feedback:.2f}, "
            f"Web Grounding: {s_web:.2f}, Consensus: {s_consensus:.2f}) -> Action: {action.value}"
        )

        return AccuracyScore(
            composite=s_composite,
            feedback=s_feedback,
            web=s_web,
            consensus=s_consensus,
            threshold_action=action,
            weights=self.weights,
            task_id=task_id,
            user_id=user_id,
            explanation=explanation,
            claims_evaluated=len(claims),
        )

