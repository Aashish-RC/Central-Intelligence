"""Bias and Fairness Measurement (Layer 11: Evaluation & Quality, Feature 11.11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class FairnessReport:
    """Fairness & demographic disparity report across demographic slices."""
    parity_gap: float
    is_fair: bool
    threshold: float
    group_scores: Dict[str, float]
    sample_sizes: Dict[str, int]


class BiasFairnessMonitor:
    """Measures demographic parity and fairness across demographic/domain slices."""

    def __init__(self, disparity_threshold: float = 0.15):
        self.disparity_threshold = disparity_threshold
        self._group_outcomes: Dict[str, List[float]] = {}

    def record_outcome(self, group: str, score: float) -> None:
        self._group_outcomes.setdefault(group, []).append(score)

    def evaluate_fairness(self) -> FairnessReport:
        if not self._group_outcomes:
            return FairnessReport(parity_gap=0.0, is_fair=True, threshold=self.disparity_threshold, group_scores={}, sample_sizes={})

        averages = {}
        counts = {}
        for grp, scores in self._group_outcomes.items():
            averages[grp] = sum(scores) / len(scores)
            counts[grp] = len(scores)

        max_val = max(averages.values())
        min_val = min(averages.values())
        gap = max_val - min_val
        is_fair = gap <= self.disparity_threshold

        return FairnessReport(
            parity_gap=round(gap, 4),
            is_fair=is_fair,
            threshold=self.disparity_threshold,
            group_scores={k: round(v, 4) for k, v in averages.items()},
            sample_sizes=counts,
        )
