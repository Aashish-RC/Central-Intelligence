"""
Per-App Observability Dashboard (Layer 14: Feature 14.17).

Provides granular metric breakdowns on a per-application / per-agent service basis:
invocation throughput, latency percentiles, error rate, and LLM token / cost attribution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from control.observability.models import PercentileMetrics
from control.observability.posthog.posthog_adapter import PostHogAdapter
from control.observability.signoz.signoz_adapter import SigNozAdapter

logger = logging.getLogger("control.observability.dashboards.per_app")


@dataclass
class AppMetricsSummary:
    """Metrics aggregated for a specific application or agent service."""
    app_id: str
    total_invocations: int
    throughput_per_minute: float
    error_count: int
    error_rate: float
    average_latency_ms: float
    percentiles: PercentileMetrics
    total_tokens: int
    total_cost_usd: float
    features_invoked: Dict[str, int] = field(default_factory=dict)


class PerAppDashboard:
    """
    Per-Application dashboard engine (Feature 14.17).
    Aggregates application-scoped telemetry from SigNoz traces and PostHog feature events.
    """

    def __init__(
        self,
        signoz_adapter: Optional[SigNozAdapter] = None,
        posthog_adapter: Optional[PostHogAdapter] = None,
    ) -> None:
        self.signoz = signoz_adapter or SigNozAdapter()
        self.posthog = posthog_adapter or PostHogAdapter()

    def list_applications(self) -> List[str]:
        """Discovers all active application identifiers across spans and events."""
        apps: Set[str] = set()
        for span in self.signoz._spans:
            app_id = span.attributes.get("app_id") or span.attributes.get("application")
            if app_id:
                apps.add(str(app_id))

        for ev in self.posthog._events:
            app_id = ev.properties.get("app_id") or ev.properties.get("application")
            if app_id:
                apps.add(str(app_id))

        return sorted(list(apps))

    def get_app_metrics(
        self,
        app_id: str,
        window_seconds: float = 3600.0,
        current_time: Optional[float] = None,
    ) -> AppMetricsSummary:
        """
        Calculates operational performance metrics for a specific application.
        """
        now = current_time if current_time is not None else time.time()
        cutoff = now - window_seconds

        # Find spans matching app_id
        app_spans = [
            s for s in self.signoz._spans
            if s.start_time >= cutoff and (
                s.attributes.get("app_id") == app_id or s.attributes.get("application") == app_id
            )
        ]
        total_invocations = len(app_spans)
        errors = sum(1 for s in app_spans if getattr(s.status, "value", str(s.status)) == "error")
        error_rate = (errors / total_invocations) if total_invocations > 0 else 0.0
        tpm = (total_invocations / (window_seconds / 60.0)) if window_seconds > 0 else 0.0

        durations = [s.duration_ms for s in app_spans if s.duration_ms > 0]
        avg_latency = (sum(durations) / len(durations)) if durations else 0.0

        if not durations:
            durations = [0.0]
        durations.sort()
        n = len(durations)
        percentiles = PercentileMetrics(
            p50_ms=durations[int(n * 0.50)],
            p90_ms=durations[min(int(n * 0.90), n - 1)],
            p95_ms=durations[min(int(n * 0.95), n - 1)],
            p99_ms=durations[min(int(n * 0.99), n - 1)],
            min_ms=durations[0],
            max_ms=durations[-1],
            sample_count=total_invocations,
        )

        # Token metrics
        app_metrics = [
            m for m in self.signoz._metrics
            if m.timestamp >= cutoff and (
                m.labels.get("app_id") == app_id or m.labels.get("application") == app_id
            )
        ]
        total_tokens = int(sum(m.value for m in app_metrics if m.name == "llm.tokens.total"))
        total_cost = sum(m.value for m in app_metrics if m.name == "llm.cost.usd")

        # Feature usage from PostHog events
        features_invoked: Dict[str, int] = {}
        for ev in self.posthog._events:
            if ev.timestamp >= cutoff:
                ev_app = ev.properties.get("app_id") or ev.properties.get("application")
                if ev_app == app_id:
                    features_invoked[ev.event_name] = features_invoked.get(ev.event_name, 0) + 1

        return AppMetricsSummary(
            app_id=app_id,
            total_invocations=total_invocations,
            throughput_per_minute=round(tpm, 2),
            error_count=errors,
            error_rate=round(error_rate, 4),
            average_latency_ms=round(avg_latency, 2),
            percentiles=percentiles,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            features_invoked=features_invoked,
        )

