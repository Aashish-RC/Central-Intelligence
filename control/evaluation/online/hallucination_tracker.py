"""Hallucination Rate Tracker (Layer 11: Evaluation & Quality, Feature 11.10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class HallucinationMetricSnapshot:
    """Snapshot of continuous hallucination metrics."""
    total_evaluated: int
    hallucination_count: int
    hallucination_rate: float
    alert_triggered: bool
    alert_threshold: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HallucinationTracker:
    """Tracks continuous sliding window hallucination rate in production."""

    def __init__(self, alert_threshold: float = 0.05, window_size: int = 100):
        self.alert_threshold = alert_threshold
        self.window_size = window_size
        self._history: List[bool] = []  # True = hallucinated, False = grounded

    def record_check(self, is_hallucinated: bool) -> HallucinationMetricSnapshot:
        self._history.append(is_hallucinated)
        if len(self._history) > self.window_size:
            self._history.pop(0)
        return self.get_snapshot()

    def get_snapshot(self) -> HallucinationMetricSnapshot:
        total = len(self._history)
        if total == 0:
            return HallucinationMetricSnapshot(
                total_evaluated=0,
                hallucination_count=0,
                hallucination_rate=0.0,
                alert_triggered=False,
                alert_threshold=self.alert_threshold,
            )

        h_count = sum(1 for h in self._history if h)
        rate = h_count / total
        alert = rate >= self.alert_threshold

        return HallucinationMetricSnapshot(
            total_evaluated=total,
            hallucination_count=h_count,
            hallucination_rate=round(rate, 4),
            alert_triggered=alert,
            alert_threshold=self.alert_threshold,
        )
