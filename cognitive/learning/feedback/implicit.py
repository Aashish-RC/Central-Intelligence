"""Implicit User Engagement Signals Tracker (L7 Feature 7.06)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ImplicitSignalEvent:
    """Captured passive engagement signal (reading time, scroll depth, copies)."""

    response_id: str
    user_id: str
    reading_time_ms: float = 0.0
    scroll_depth_pct: float = 0.0
    copy_count: int = 0
    revisit_count: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class EngagementSummary:
    """Inferred engagement summary for a response without explicit ratings."""

    response_id: str
    total_reading_time_ms: float
    max_scroll_depth_pct: float
    total_copies: int
    engagement_score: float  # normalized [0.0, 1.0]


class ImplicitSignalTracker:
    """Infers output usefulness from reading duration, scroll depth, and copies."""

    def __init__(self) -> None:
        self._by_response: Dict[str, List[ImplicitSignalEvent]] = {}

    def record_signal(
        self,
        response_id: str,
        user_id: str,
        reading_time_ms: float = 0.0,
        scroll_depth_pct: float = 0.0,
        copy_count: int = 0,
        revisit_count: int = 0,
    ) -> ImplicitSignalEvent:
        evt = ImplicitSignalEvent(
            response_id=response_id,
            user_id=user_id,
            reading_time_ms=max(0.0, reading_time_ms),
            scroll_depth_pct=max(0.0, min(100.0, scroll_depth_pct)),
            copy_count=max(0, copy_count),
            revisit_count=max(0, revisit_count),
        )
        self._by_response.setdefault(response_id, []).append(evt)
        return evt

    def summarize_response(self, response_id: str) -> EngagementSummary:
        events = self._by_response.get(response_id, [])
        if not events:
            return EngagementSummary(response_id, 0.0, 0.0, 0, 0.0)

        total_ms = sum(e.reading_time_ms for e in events)
        max_scroll = max(e.scroll_depth_pct for e in events)
        copies = sum(e.copy_count for e in events)

        # Normalize: 30s read -> 0.45 weight, 100% scroll -> 0.25, copy -> 0.30
        read_comp = min(1.0, total_ms / 30_000.0) * 0.45
        scroll_comp = (max_scroll / 100.0) * 0.25
        copy_comp = (0.30 if copies > 0 else 0.0)
        score = round(min(1.0, read_comp + scroll_comp + copy_comp), 4)

        return EngagementSummary(
            response_id=response_id,
            total_reading_time_ms=total_ms,
            max_scroll_depth_pct=max_scroll,
            total_copies=copies,
            engagement_score=score,
        )

