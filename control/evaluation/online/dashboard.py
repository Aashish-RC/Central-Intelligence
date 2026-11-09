"""Live Online Quality Monitoring Dashboard (Layer 11: Evaluation & Quality, Features 11.06-11.13).

Aggregates hallucination tracking, distribution drift, demographic bias, and user satisfaction trends.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .auto_judge import AutoJudge
from .bias_fairness import BiasFairnessMonitor, FairnessReport
from .drift_detector import DriftStatus, OnlineDriftDetector
from .failure_clusterer import FailureClusterer
from .hallucination_tracker import HallucinationMetricSnapshot, HallucinationTracker
from .human_review import HumanReviewQueue
from .quality_bar import QualityBarManager
from .satisfaction import SatisfactionMetrics, SatisfactionTracker


@dataclass
class QualityDashboardSnapshot:
    """Consolidated snapshot of live online evaluation health."""
    hallucination: HallucinationMetricSnapshot
    drift: DriftStatus
    bias_fairness: FairnessReport
    satisfaction: SatisfactionMetrics

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OnlineQualityMonitor:
    """Unified telemetry hub collecting and aggregating live quality telemetry."""

    def __init__(self):
        self.auto_judge = AutoJudge()
        self.human_review = HumanReviewQueue()
        self.drift_detector = OnlineDriftDetector()
        self.failure_clusterer = FailureClusterer()
        self.hallucination_tracker = HallucinationTracker()
        self.bias_monitor = BiasFairnessMonitor()
        self.quality_bar_mgr = QualityBarManager()
        self.satisfaction_tracker = SatisfactionTracker()

    def get_dashboard_snapshot(self) -> QualityDashboardSnapshot:
        return QualityDashboardSnapshot(
            hallucination=self.hallucination_tracker.get_snapshot(),
            drift=self.drift_detector.check_drift(),
            bias_fairness=self.bias_monitor.evaluate_fairness(),
            satisfaction=self.satisfaction_tracker.get_metrics(),
        )

