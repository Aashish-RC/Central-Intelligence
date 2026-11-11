"""Acceptance Feedback Tracking (L7 Feature 7.04)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AcceptanceAction(str, Enum):
    USE_THIS = "use_this"
    COPY = "copy"
    EXPORT = "export"
    APPLY_DIFF = "apply_diff"
    DISMISS = "dismiss"


@dataclass
class AcceptanceEvent:
    """Explicit or implicit user acceptance/dismissal of a generated output."""

    response_id: str
    user_id: str
    action: AcceptanceAction
    model_id: str = "default"
    timestamp: float = field(default_factory=time.time)

    @property
    def is_accepted(self) -> bool:
        return self.action != AcceptanceAction.DISMISS


@dataclass
class AcceptanceStats:
    total_events: int
    accepted_count: int
    dismissed_count: int
    acceptance_rate: float
    by_action: Dict[str, int] = field(default_factory=dict)


class AcceptanceTracker:
    """Records output acceptance actions and computes acceptance rates."""

    def __init__(self) -> None:
        self._events: List[AcceptanceEvent] = []

    def record(
        self,
        response_id: str,
        user_id: str,
        action: AcceptanceAction,
        model_id: str = "default",
    ) -> AcceptanceEvent:
        evt = AcceptanceEvent(
            response_id=response_id,
            user_id=user_id,
            action=action,
            model_id=model_id,
        )
        self._events.append(evt)
        return evt

    def get_stats(self, model_id: Optional[str] = None) -> AcceptanceStats:
        filtered = [e for e in self._events if model_id is None or e.model_id == model_id]
        if not filtered:
            return AcceptanceStats(0, 0, 0, 0.0)
        accepted = sum(1 for e in filtered if e.is_accepted)
        dismissed = len(filtered) - accepted
        by_action: Dict[str, int] = {}
        for e in filtered:
            by_action[e.action.value] = by_action.get(e.action.value, 0) + 1
        return AcceptanceStats(
            total_events=len(filtered),
            accepted_count=accepted,
            dismissed_count=dismissed,
            acceptance_rate=round(accepted / len(filtered), 4),
            by_action=by_action,
        )

