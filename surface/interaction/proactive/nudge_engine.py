"""Proactive Nudge Engine (L18 Interaction - Tasks 18.18-18.24).

Generates event-driven and time-scheduled proactive nudges, routes high-priority
alerts immediately across all client surfaces, and aggregates routine digests
(e.g., Daily brief at 9:00 AM).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NudgePriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    ROUTINE = "routine"
    DIGEST = "digest"


class NudgeTriggerType(str, Enum):
    EVENT = "event"
    SCHEDULED_TIME = "scheduled_time"
    INACTIVITY = "inactivity"


@dataclass
class Nudge:
    """A proactive notification or scheduled digest unit."""
    nudge_id: str
    title: str
    message: str
    priority: NudgePriority
    trigger_type: NudgeTriggerType
    target_surfaces: List[str] = field(default_factory=lambda: ["desktop", "mobile", "web"])
    scheduled_for: float = field(default_factory=time.time)
    dispatched: bool = False
    dispatched_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProactiveNudgeEngine:
    """Manages proactive alert scheduling, cross-app routing, and immediate urgent dispatches."""

    def __init__(self) -> None:
        self._nudges: Dict[str, Nudge] = {}
        self._dispatched_nudges: List[Nudge] = []
        self._listeners: List[Callable[[Nudge], None]] = []

    def add_listener(self, listener: Callable[[Nudge], None]) -> None:
        """Register cross-app delivery listener."""
        self._listeners.append(listener)

    def dispatch_urgent_nudge(
        self,
        title: str,
        message: str,
        target_surfaces: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Nudge:
        """Dispatch an urgent, critical nudge immediately with zero delay."""
        nudge_id = f"ndg_urg_{uuid.uuid4().hex[:8]}"
        nudge = Nudge(
            nudge_id=nudge_id,
            title=title,
            message=message,
            priority=NudgePriority.URGENT,
            trigger_type=NudgeTriggerType.EVENT,
            target_surfaces=target_surfaces or ["desktop", "mobile", "web", "ide"],
            scheduled_for=time.time(),
            dispatched=True,
            dispatched_at=time.time(),
            metadata=metadata or {},
        )
        self._nudges[nudge_id] = nudge
        self._dispatched_nudges.append(nudge)

        for listener in self._listeners:
            try:
                listener(nudge)
            except Exception as exc:
                logger.error("Error in nudge listener: %s", exc)

        logger.info("Urgent nudge '%s' dispatched immediately to %s", title, nudge.target_surfaces)
        return nudge

    def schedule_daily_brief(
        self,
        title: str = "Daily Morning Brief",
        message: str = "Your daily agenda and critical metrics are ready.",
        scheduled_timestamp: Optional[float] = None,
    ) -> Nudge:
        """Schedule routine morning brief for 9:00 AM or designated timestamp."""
        nudge_id = f"ndg_sched_{uuid.uuid4().hex[:8]}"
        sched_time = scheduled_timestamp if scheduled_timestamp is not None else (time.time() + 3600.0)

        nudge = Nudge(
            nudge_id=nudge_id,
            title=title,
            message=message,
            priority=NudgePriority.DIGEST,
            trigger_type=NudgeTriggerType.SCHEDULED_TIME,
            target_surfaces=["desktop", "mobile", "web"],
            scheduled_for=sched_time,
            dispatched=False,
        )
        self._nudges[nudge_id] = nudge
        logger.info("Scheduled digest '%s' for timestamp %.0f", title, sched_time)
        return nudge

    def poll_due_nudges(self, current_time: Optional[float] = None) -> List[Nudge]:
        """Poll and dispatch all scheduled nudges that are due for delivery."""
        now = current_time if current_time is not None else time.time()
        due_list = []

        for nudge in self._nudges.values():
            if not nudge.dispatched and nudge.scheduled_for <= now:
                nudge.dispatched = True
                nudge.dispatched_at = now
                self._dispatched_nudges.append(nudge)
                due_list.append(nudge)

                for listener in self._listeners:
                    try:
                        listener(nudge)
                    except Exception as exc:
                        logger.error("Error in nudge listener: %s", exc)

        return due_list

    def get_dispatched_history(self) -> List[Nudge]:
        return list(self._dispatched_nudges)
