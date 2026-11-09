"""User Satisfaction Trends & CSAT Scoring (Layer 11: Evaluation & Quality, Feature 11.13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class SatisfactionFeedback:
    """Explicit feedback signal from user."""
    feedback_id: str
    user_id: str
    trace_id: str
    rating: int  # 1 to 5 stars or 1=positive, 0=negative
    comment: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SatisfactionMetrics:
    """Aggregated CSAT metrics and trends."""
    total_feedbacks: int
    csat_score: float  # Percentage of positive ratings (>= 4 stars or == 1)
    average_rating: float
    trend: str  # 'improving', 'stable', 'declining'


class SatisfactionTracker:
    """Tracks continuous user satisfaction and CSAT rating trends."""

    def __init__(self):
        self._feedbacks: List[SatisfactionFeedback] = []

    def record_feedback(
        self,
        feedback_id: str,
        user_id: str,
        trace_id: str,
        rating: int,
        comment: Optional[str] = None,
    ) -> SatisfactionFeedback:
        fb = SatisfactionFeedback(
            feedback_id=feedback_id,
            user_id=user_id,
            trace_id=trace_id,
            rating=rating,
            comment=comment,
        )
        self._feedbacks.append(fb)
        return fb

    def get_metrics(self) -> SatisfactionMetrics:
        if not self._feedbacks:
            return SatisfactionMetrics(
                total_feedbacks=0,
                csat_score=1.0,
                average_rating=5.0,
                trend="stable",
            )

        total = len(self._feedbacks)
        ratings = [f.rating for f in self._feedbacks]
        avg_rating = sum(ratings) / total

        # Consider positive if 1 (binary) or >= 4 (5-point scale)
        positive = sum(1 for r in ratings if r >= 4 or r == 1)
        csat = positive / total

        # Compute trend between first half and second half if enough data
        trend = "stable"
        if total >= 4:
            mid = total // 2
            h1 = sum(ratings[:mid]) / mid
            h2 = sum(ratings[mid:]) / (total - mid)
            if h2 - h1 > 0.3:
                trend = "improving"
            elif h1 - h2 > 0.3:
                trend = "declining"

        return SatisfactionMetrics(
            total_feedbacks=total,
            csat_score=round(csat, 4),
            average_rating=round(avg_rating, 2),
            trend=trend,
        )

