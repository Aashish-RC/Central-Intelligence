"""Online Drift Detection (Layer 11: Evaluation & Quality, Feature 11.08)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class DriftStatus:
    """Drift evaluation report."""
    is_drifted: bool
    drift_score: float
    threshold: float
    window_size: int
    mean_baseline: float
    mean_current: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OnlineDriftDetector:
    """Monitors distribution drift of production metric streams (lengths, latencies, confidence)."""

    def __init__(self, threshold: float = 0.20, window_size: int = 50):
        self.threshold = threshold
        self.window_size = window_size
        self._baseline_distribution: List[float] = []
        self._current_window: List[float] = []

    def set_baseline(self, values: List[float]) -> None:
        self._baseline_distribution = list(values)

    def record_observation(self, value: float) -> Optional[DriftStatus]:
        self._current_window.append(value)
        if len(self._current_window) > self.window_size:
            self._current_window.pop(0)

        if len(self._baseline_distribution) >= 10 and len(self._current_window) >= self.window_size:
            return self.check_drift()
        return None

    def check_drift(self) -> DriftStatus:
        if not self._baseline_distribution or not self._current_window:
            return DriftStatus(
                is_drifted=False,
                drift_score=0.0,
                threshold=self.threshold,
                window_size=len(self._current_window),
                mean_baseline=0.0,
                mean_current=0.0,
            )

        mean_base = sum(self._baseline_distribution) / len(self._baseline_distribution)
        mean_curr = sum(self._current_window) / len(self._current_window)

        # Normalized relative shift
        denom = max(abs(mean_base), 1e-6)
        shift = abs(mean_curr - mean_base) / denom
        is_drifted = shift >= self.threshold

        return DriftStatus(
            is_drifted=is_drifted,
            drift_score=round(shift, 4),
            threshold=self.threshold,
            window_size=len(self._current_window),
            mean_baseline=round(mean_base, 4),
            mean_current=round(mean_curr, 4),
        )

