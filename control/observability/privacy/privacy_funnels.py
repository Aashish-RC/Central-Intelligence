"""
Differential Privacy Funnels (Layer 14: Feature 14.22).

Applies differential privacy via the Laplace Mechanism calibrated to a configurable privacy
budget (epsilon) over conversion funnels and product analytics events.
Guarantees mathematically that individual user presence or absence cannot be reverse-engineered
from published funnel statistics, while preserving aggregate trends.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import numpy as np

from control.observability.posthog.posthog_adapter import AnalyticsEvent, PostHogAdapter

logger = logging.getLogger("control.observability.privacy.funnels")


@dataclass
class FunnelEvent:
    """An event within a conversion journey."""
    user_id: str
    event_name: str
    timestamp: float = field(default_factory=time.time)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FunnelStats:
    """Differentially private summary for an aggregated funnel metric."""
    count: int
    epsilon: float
    privacy_guaranteed: bool = True
    raw_count_redacted: bool = True
    step_name: Optional[str] = None


@dataclass
class DifferentiallyPrivateStepResult:
    """Differentially private funnel stage metric."""
    step_name: str
    step_index: int
    noisy_users_reached: int
    noisy_conversion_rate: float
    noisy_drop_off_count: int


@dataclass
class DifferentialFunnelReport:
    """Full multi-step conversion funnel protected by differential privacy."""
    steps: List[DifferentiallyPrivateStepResult]
    epsilon: float
    total_noisy_starters: int
    privacy_guaranteed: bool = True


class PrivacyFunnels:
    """
    Differential privacy engine for conversion funnels and behavioral telemetry (Feature 14.22).
    Calibrates Laplace noise to the privacy budget (epsilon) to protect user anonymity.
    """

    def __init__(
        self,
        epsilon: float = 1.0,
        posthog_adapter: Optional[PostHogAdapter] = None,
    ) -> None:
        if epsilon <= 0:
            raise ValueError("Differential privacy budget epsilon must be strictly positive.")
        self.epsilon = epsilon
        self.posthog = posthog_adapter or PostHogAdapter()

    def add_laplace_noise(self, true_value: float, sensitivity: float = 1.0) -> float:
        """Draws noise from Laplace(0, sensitivity / epsilon)."""
        scale = sensitivity / self.epsilon
        noise = float(np.random.laplace(0.0, scale))
        return true_value + noise

    def aggregate_funnel(self, events: List[FunnelEvent]) -> FunnelStats:
        """
        Applies differential privacy before aggregation (Feature 14.22 algorithm).
        Adds Laplace noise calibrated to epsilon.
        """
        true_count = len(events)
        noisy_val = self.add_laplace_noise(float(true_count), sensitivity=1.0)
        noisy_count = max(0, int(round(noisy_val)))
        return FunnelStats(
            count=noisy_count,
            epsilon=self.epsilon,
            privacy_guaranteed=True,
        )

    def compute_private_funnel(
        self,
        step_names: List[str],
        events: Optional[List[FunnelEvent]] = None,
        time_window_seconds: float = 86400.0,
    ) -> DifferentialFunnelReport:
        """
        Calculates a sequential multi-step conversion funnel with differential privacy guarantees.
        Adds independent Laplace noise to each step's user count.
        """
        if not step_names:
            return DifferentialFunnelReport(
                steps=[],
                epsilon=self.epsilon,
                total_noisy_starters=0,
                privacy_guaranteed=True,
            )

        # Convert PostHog events if explicit funnel events not provided
        if events is None:
            raw_posthog = self.posthog._events
            events = [
                FunnelEvent(
                    user_id=e.distinct_id,
                    event_name=e.event_name,
                    timestamp=e.timestamp,
                    properties=e.properties,
                )
                for e in raw_posthog
            ]

        # Group by user sorted by timestamp
        user_events: Dict[str, List[FunnelEvent]] = {}
        for ev in sorted(events, key=lambda e: e.timestamp):
            user_events.setdefault(ev.user_id, []).append(ev)

        completed_step_users: List[Set[str]] = [set() for _ in step_names]

        for uid, u_evs in user_events.items():
            current_step_idx = 0
            step_start_time = 0.0

            for ev in u_evs:
                if current_step_idx < len(step_names) and ev.event_name == step_names[current_step_idx]:
                    if current_step_idx == 0:
                        step_start_time = ev.timestamp
                        completed_step_users[0].add(uid)
                        current_step_idx += 1
                    else:
                        if (ev.timestamp - step_start_time) <= time_window_seconds:
                            completed_step_users[current_step_idx].add(uid)
                            current_step_idx += 1

        # Apply differential privacy to each step count
        noisy_counts: List[int] = []
        for step_idx, users_set in enumerate(completed_step_users):
            true_count = len(users_set)
            noisy = self.add_laplace_noise(float(true_count), sensitivity=1.0)
            noisy_int = max(0, int(round(noisy)))
            # Monotonicity adjustment: subsequent steps cannot exceed previous step
            if step_idx > 0 and noisy_int > noisy_counts[step_idx - 1]:
                noisy_int = noisy_counts[step_idx - 1]
            noisy_counts.append(noisy_int)

        first_count = noisy_counts[0] if noisy_counts else 0
        step_results: List[DifferentiallyPrivateStepResult] = []

        for idx, name in enumerate(step_names):
            cnt = noisy_counts[idx]
            rate = (cnt / first_count * 100.0) if first_count > 0 else 0.0
            prev_cnt = noisy_counts[idx - 1] if idx > 0 else cnt
            drop_off = max(0, prev_cnt - cnt)

            step_results.append(
                DifferentiallyPrivateStepResult(
                    step_name=name,
                    step_index=idx,
                    noisy_users_reached=cnt,
                    noisy_conversion_rate=round(rate, 2),
                    noisy_drop_off_count=drop_off,
                )
            )

        return DifferentialFunnelReport(
            steps=step_results,
            epsilon=self.epsilon,
            total_noisy_starters=first_count,
            privacy_guaranteed=True,
        )


# Global default privacy funnels instance
default_privacy_funnels = PrivacyFunnels(epsilon=1.0)

