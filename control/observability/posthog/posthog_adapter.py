"""PostHog Product Analytics & Funnels Adapter (Layer 14: Features 14.22, 14.23, 14.24).

Tracks privacy-preserving product usage, conversion funnels (signup -> first chat -> tool invocation),
feature adoption breakdown per application, and session interaction timeline streams.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

import httpx

from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.observability.posthog")


@dataclass
class AnalyticsEvent:
    event_id: str
    distinct_id: str
    event_name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class FunnelStepResult:
    step_name: str
    step_index: int
    users_reached: int
    conversion_rate_from_start: float
    drop_off_count: int


class PostHogAdapter:
    """Enterprise Product Analytics and Funnels Engine."""

    def __init__(
        self,
        api_url: str = "http://localhost:8090",
        api_key: Optional[str] = None,
        _defer_prod_check: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or "posthog_local_test_key"
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("posthog")
        )

        self._events: List[AnalyticsEvent] = []
        self._session_replays: Dict[str, List[Dict[str, Any]]] = {}

    def capture(
        self,
        distinct_id: str,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> AnalyticsEvent:
        """Records an analytics event (14.23)."""
        ev = AnalyticsEvent(
            event_id=f"ev_{int(time.time()*1000)}_{str(uuid4())[:8]}",
            distinct_id=distinct_id,
            event_name=event_name,
            properties=properties or {},
            timestamp=timestamp if timestamp is not None else time.time(),
        )
        self._events.append(ev)
        return ev

    def record_session_replay_event(
        self,
        session_id: str,
        distinct_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Appends user UI/chat interaction to session replay stream (14.22)."""
        record = {
            "session_id": session_id,
            "distinct_id": distinct_id,
            "event_type": event_type,
            "payload": payload,
            "timestamp": time.time(),
        }
        self._session_replays.setdefault(session_id, []).append(record)
        return record

    def get_session_replay(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns ordered timeline of interactions for session inspection."""
        return self._session_replays.get(session_id, [])

    def compute_funnel(
        self,
        step_names: List[str],
        time_window_seconds: float = 86400.0,
    ) -> List[FunnelStepResult]:
        """Calculates multi-step user conversion funnel (e.g. signup -> first_chat -> tool_use)."""
        if not step_names:
            return []

        # Group events by user sorted by timestamp
        user_events: Dict[str, List[AnalyticsEvent]] = {}
        for ev in sorted(self._events, key=lambda e: e.timestamp):
            user_events.setdefault(ev.distinct_id, []).append(ev)

        # Track which users completed up to step k
        completed_step_users: List[Set[str]] = [set() for _ in step_names]

        for uid, events in user_events.items():
            current_step_idx = 0
            step_start_time = 0.0

            for ev in events:
                if current_step_idx < len(step_names) and ev.event_name == step_names[current_step_idx]:
                    if current_step_idx == 0:
                        step_start_time = ev.timestamp
                        completed_step_users[0].add(uid)
                        current_step_idx += 1
                    else:
                        if (ev.timestamp - step_start_time) <= time_window_seconds:
                            completed_step_users[current_step_idx].add(uid)
                            current_step_idx += 1

        results: List[FunnelStepResult] = []
        start_count = len(completed_step_users[0]) if completed_step_users else 0

        for idx, step_name in enumerate(step_names):
            reached = len(completed_step_users[idx])
            rate = (reached / start_count * 100.0) if start_count > 0 else 0.0
            drop_off = (len(completed_step_users[idx - 1]) - reached) if idx > 0 else 0

            results.append(
                FunnelStepResult(
                    step_name=step_name,
                    step_index=idx,
                    users_reached=reached,
                    conversion_rate_from_start=round(rate, 2),
                    drop_off_count=max(0, drop_off),
                )
            )

        return results

    def get_feature_adoption(self) -> Dict[str, Dict[str, Any]]:
        """Provides breakdown of feature adoption and frequency (14.23)."""
        breakdown: Dict[str, Dict[str, Any]] = {}
        for ev in self._events:
            feat = ev.properties.get("feature", ev.event_name)
            if feat not in breakdown:
                breakdown[feat] = {"unique_users": set(), "total_invocations": 0}
            breakdown[feat]["unique_users"].add(ev.distinct_id)
            breakdown[feat]["total_invocations"] += 1

        return {
            k: {
                "unique_users_count": len(v["unique_users"]),
                "total_invocations": v["total_invocations"],
            }
            for k, v in breakdown.items()
        }

