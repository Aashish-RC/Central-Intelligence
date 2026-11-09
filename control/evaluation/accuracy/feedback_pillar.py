"""Feedback Pillar: S_feedback (Layer 11: Evaluation & Quality, Feature 11.14).

Computes aggregated user feedback score from explicit ratings, corrections, and rejections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class FeedbackSignal:
    """Explicit or implicit feedback event."""
    user_id: str
    task_id: str
    rating: float  # 0.0 (negative / rejected) to 1.0 (thumbs up / accepted)
    weight: float = 1.0
    was_edited: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FeedbackPillar:
    """Calculates historical and contextual user feedback score S_feedback."""

    def __init__(self, default_neutral_score: float = 0.80):
        self.default_neutral_score = default_neutral_score
        self._user_history: Dict[str, List[FeedbackSignal]] = {}
        self._task_feedback: Dict[str, List[FeedbackSignal]] = {}

    def record_feedback(
        self,
        user_id: str,
        task_id: str,
        rating: float,
        weight: float = 1.0,
        was_edited: bool = False,
    ) -> FeedbackSignal:
        signal = FeedbackSignal(
            user_id=user_id,
            task_id=task_id,
            rating=max(0.0, min(1.0, rating)),
            weight=weight,
            was_edited=was_edited,
        )
        self._user_history.setdefault(user_id, []).append(signal)
        self._task_feedback.setdefault(task_id, []).append(signal)
        return signal

    def get_feedback_score(self, user_id: Optional[str] = None, task_id: Optional[str] = None) -> float:
        """Computes weighted average feedback score."""
        signals: List[FeedbackSignal] = []

        if task_id and task_id in self._task_feedback:
            signals = self._task_feedback[task_id]
        elif user_id and user_id in self._user_history:
            signals = self._user_history[user_id][-20:]  # Recent 20 signals

        if not signals:
            return self.default_neutral_score

        weighted_sum = sum(s.rating * s.weight for s in signals)
        total_weight = sum(s.weight for s in signals)
        if total_weight == 0:
            return self.default_neutral_score

        return round(weighted_sum / total_weight, 4)
