"""Action Thresholds and Transparency Settings (Layer 11: Evaluation & Quality, Features 11.16, 11.17)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThresholdAction(str, Enum):
    DELIVER = "deliver"
    FLAG_LOW_CONFIDENCE = "flag_low_confidence"
    TRIGGER_SECOND_OPINION = "trigger_second_opinion"  # DEF-03 unblock trigger


@dataclass
class AccuracyThresholdConfig:
    """Configurable thresholds for accuracy score actions."""
    deliver_threshold: float = 0.80
    second_opinion_threshold: float = 0.50
    user_visibility_enabled: bool = True  # Transparency panel in client surfaces

    def evaluate_action(self, score: float) -> ThresholdAction:
        if score >= self.deliver_threshold:
            return ThresholdAction.DELIVER
        elif score >= self.second_opinion_threshold:
            return ThresholdAction.FLAG_LOW_CONFIDENCE
        else:
            return ThresholdAction.TRIGGER_SECOND_OPINION
