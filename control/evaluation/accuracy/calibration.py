"""Calibration Scoring: Stated Confidence vs Actual Outcomes (Layer 11: Evaluation & Quality, Feature 11.15)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple


@dataclass
class CalibrationSample:
    """Pair of stated confidence and ground-truth binary outcome."""
    stated_confidence: float  # e.g. 0.90
    actual_outcome: bool      # e.g. True (correct) or False (incorrect)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CalibrationBin:
    """Discretized bin for reliability diagram."""
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_confidence: float
    accuracy: float


@dataclass
class CalibrationCurveReport:
    """Expected Calibration Error (ECE) and bin summary."""
    expected_calibration_error: float  # ECE
    max_calibration_error: float       # MCE
    total_samples: int
    bins: List[CalibrationBin]
    well_calibrated: bool  # True if ECE <= threshold (e.g. 0.10)


class ConfidenceCalibrator:
    """Tracks and evaluates whether stated confidence matches empirical probability of correctness."""

    def __init__(self, num_bins: int = 10, ece_threshold: float = 0.10):
        self.num_bins = num_bins
        self.ece_threshold = ece_threshold
        self._samples: List[CalibrationSample] = []

    def record_prediction(self, stated_confidence: float, actual_outcome: bool) -> None:
        self._samples.append(
            CalibrationSample(
                stated_confidence=max(0.0, min(1.0, stated_confidence)),
                actual_outcome=actual_outcome,
            )
        )

    def calculate_calibration(self) -> CalibrationCurveReport:
        if not self._samples:
            return CalibrationCurveReport(
                expected_calibration_error=0.0,
                max_calibration_error=0.0,
                total_samples=0,
                bins=[],
                well_calibrated=True,
            )

        total_n = len(self._samples)
        bin_width = 1.0 / self.num_bins
        bins: List[CalibrationBin] = []
        ece = 0.0
        mce = 0.0

        for i in range(self.num_bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width
            # Select samples in this bin
            bin_samples = [
                s for s in self._samples
                if (lower <= s.stated_confidence < upper) or (i == self.num_bins - 1 and s.stated_confidence == upper)
            ]

            if not bin_samples:
                bins.append(
                    CalibrationBin(
                        bin_lower=round(lower, 2),
                        bin_upper=round(upper, 2),
                        sample_count=0,
                        mean_confidence=round((lower + upper) / 2.0, 2),
                        accuracy=0.0,
                    )
                )
                continue

            n_b = len(bin_samples)
            mean_conf = sum(s.stated_confidence for s in bin_samples) / n_b
            acc = sum(1 for s in bin_samples if s.actual_outcome) / n_b
            gap = abs(mean_conf - acc)

            ece += (n_b / total_n) * gap
            mce = max(mce, gap)

            bins.append(
                CalibrationBin(
                    bin_lower=round(lower, 2),
                    bin_upper=round(upper, 2),
                    sample_count=n_b,
                    mean_confidence=round(mean_conf, 4),
                    accuracy=round(acc, 4),
                )
            )

        return CalibrationCurveReport(
            expected_calibration_error=round(ece, 4),
            max_calibration_error=round(mce, 4),
            total_samples=total_n,
            bins=bins,
            well_calibrated=ece <= self.ece_threshold,
        )

