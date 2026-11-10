"""
Real-Time System Dashboard (Layer 14: Feature 14.15).

Aggregates real-time operational metrics across all services, layers, and tenants:
live request throughput, latency distribution percentiles (p50/p90/p95/p99), error rates,
token processing rates, and active trace spans.
Enforces admin authorization for global system observability.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control.observability.models import PercentileMetrics, SpanRecord, TraceStatus
from control.observability.signoz.signoz_adapter import SigNozAdapter

logger = logging.getLogger("control.observability.dashboards.realtime")


@dataclass
class SystemRealtimeMetrics:
    """Snapshot of real-time cluster health and performance."""
    timestamp: float
    window_seconds: float
    total_requests: int
    throughput_rps: float
    error_count: int
    error_rate: float
    percentiles: PercentileMetrics
    total_tokens_processed: int
    token_rate_per_sec: float
    total_cost_usd: float
    active_spans_count: int


class RealtimeDashboard:
    """
    Real-time system observability dashboard (Feature 14.15).
    Provides cluster-wide telemetry aggregation.
    """

    def __init__(self, signoz_adapter: Optional[SigNozAdapter] = None) -> None:
        self.signoz = signoz_adapter or SigNozAdapter()

    def get_system_metrics(
        self,
        requester_role: str = "admin",
        window_seconds: float = 300.0,
        current_time: Optional[float] = None,
    ) -> SystemRealtimeMetrics:
        """
        Returns real-time cluster metrics for the requested time window.
        Enforces admin authorization.
        """
        if requester_role != "admin":
            raise PermissionError("Access denied: Real-time system dashboard requires admin privileges.")

        now = current_time if current_time is not None else time.time()
        cutoff = now - window_seconds

        # Filter spans within window
        window_spans = [
            s for s in self.signoz._spans
            if s.start_time >= cutoff
        ]
        total_requests = len(window_spans)
        errors = sum(1 for s in window_spans if s.status == TraceStatus.ERROR)
        error_rate = (errors / total_requests) if total_requests > 0 else 0.0
        rps = (total_requests / window_seconds) if window_seconds > 0 else 0.0

        # Latencies
        durations = [s.duration_ms for s in window_spans if s.duration_ms > 0]
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
            sample_count=total_requests,
        )

        # Filter metrics within window
        window_metrics = [
            m for m in self.signoz._metrics
            if m.timestamp >= cutoff
        ]

        total_tokens = int(sum(
            m.value for m in window_metrics
            if m.name == "llm.tokens.total"
        ))
        token_rate = (total_tokens / window_seconds) if window_seconds > 0 else 0.0
        total_cost = sum(
            m.value for m in window_metrics
            if m.name == "llm.cost.usd"
        )

        active_spans = sum(1 for s in window_spans if s.end_time is None)

        return SystemRealtimeMetrics(
            timestamp=now,
            window_seconds=window_seconds,
            total_requests=total_requests,
            throughput_rps=round(rps, 2),
            error_count=errors,
            error_rate=round(error_rate, 4),
            percentiles=percentiles,
            total_tokens_processed=total_tokens,
            token_rate_per_sec=round(token_rate, 2),
            total_cost_usd=round(total_cost, 4),
            active_spans_count=active_spans,
        )

