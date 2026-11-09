"""Human Review Sampling and Annotation Queue (Layer 11: Evaluation & Quality, Feature 11.07)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


@dataclass
class ReviewItem:
    """Item queued for human review."""
    item_id: str
    trace_id: str
    prompt: str
    response: str
    confidence_score: float
    status: ReviewStatus = ReviewStatus.PENDING
    sampling_reason: str = "random"
    reviewer_id: Optional[str] = None
    reviewer_feedback: Optional[str] = None
    corrected_response: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanReviewQueue:
    """Manages sampling policies and queueing for human evaluation and auditing."""

    def __init__(self, random_sample_rate: float = 0.05, low_confidence_threshold: float = 0.50):
        self.random_sample_rate = random_sample_rate
        self.low_confidence_threshold = low_confidence_threshold
        self._queue: Dict[str, ReviewItem] = {}

    def maybe_sample(
        self,
        trace_id: str,
        prompt: str,
        response: str,
        confidence_score: float,
        force_sample: bool = False,
    ) -> Optional[ReviewItem]:
        reason: Optional[str] = None

        if force_sample:
            reason = "forced"
        elif confidence_score < self.low_confidence_threshold:
            reason = "low_confidence"
        elif random.random() < self.random_sample_rate:
            reason = "random_sample"

        if not reason:
            return None

        item_id = f"rev-{trace_id}"
        item = ReviewItem(
            item_id=item_id,
            trace_id=trace_id,
            prompt=prompt,
            response=response,
            confidence_score=confidence_score,
            sampling_reason=reason,
        )
        self._queue[item_id] = item
        return item

    def get_pending_reviews(self) -> List[ReviewItem]:
        return [i for i in self._queue.values() if i.status == ReviewStatus.PENDING]

    def submit_review(
        self,
        item_id: str,
        status: ReviewStatus,
        reviewer_id: str,
        feedback: Optional[str] = None,
        corrected_response: Optional[str] = None,
    ) -> ReviewItem:
        if item_id not in self._queue:
            raise KeyError(f"Review item {item_id} not found")
        item = self._queue[item_id]
        item.status = status
        item.reviewer_id = reviewer_id
        item.reviewer_feedback = feedback
        item.corrected_response = corrected_response
        return item
