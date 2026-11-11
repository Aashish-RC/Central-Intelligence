"""1-5 Star Ratings Store & Aggregation (L7 Feature 7.05)."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RatingEntry:
    """Single 1-to-5 star user rating on an AI response."""

    response_id: str
    user_id: str
    stars: int
    model_id: str = "default"
    comment: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not (1 <= int(self.stars) <= 5):
            raise ValueError(f"Star rating must be between 1 and 5, got {self.stars}")
        self.stars = int(self.stars)


@dataclass
class RatingAggregation:
    count: int
    average_stars: float
    distribution: Dict[int, int] = field(default_factory=dict)


class RatingsStore:
    """Stores and aggregates 1-5 star ratings across models and responses."""

    def __init__(self) -> None:
        self._entries: List[RatingEntry] = []

    def add_rating(
        self,
        response_id: str,
        user_id: str,
        stars: int,
        model_id: str = "default",
        comment: str = "",
    ) -> RatingEntry:
        entry = RatingEntry(
            response_id=response_id,
            user_id=user_id,
            stars=stars,
            model_id=model_id,
            comment=comment,
        )
        self._entries.append(entry)
        return entry

    def aggregate(self, model_id: Optional[str] = None) -> RatingAggregation:
        filtered = [e for e in self._entries if model_id is None or e.model_id == model_id]
        dist = {i: 0 for i in range(1, 6)}
        if not filtered:
            return RatingAggregation(count=0, average_stars=0.0, distribution=dist)
        for e in filtered:
            dist[e.stars] += 1
        avg = round(statistics.mean(e.stars for e in filtered), 3)
        return RatingAggregation(count=len(filtered), average_stars=avg, distribution=dist)

