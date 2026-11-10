"""
Executive Observability Dashboard (Layer 14: Feature 14.18).

Provides leadership and operations teams with executive-level visibility:
high-level KPIs, total infrastructure & LLM costs, aggregate tenant usage trends,
model cost breakdown, and overall system availability uptime.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from control.observability.signoz.signoz_adapter import SigNozAdapter
from control.observability.uptime.uptime_kuma_adapter import UptimeKumaAdapter

logger = logging.getLogger("control.observability.dashboards.executive")


@dataclass
class ExecutiveKPISummary:
    """High-level executive metrics and aggregate operational KPIs."""
    timestamp: float
    time_window_hours: float
    total_cost_usd: float
    total_tokens_consumed: int
    total_requests: int
    active_tenants_count: int
    active_users_count: int
    uptime_percentage: float
    top_tenants_by_spend: List[Dict[str, Any]]
    model_cost_breakdown: Dict[str, float]
    average_system_latency_ms: float
    overall_error_rate: float


class ExecutiveDashboard:
    """
    Executive dashboard aggregation engine (Feature 14.18).
    Rolls up organization-wide telemetry for executive decision making.
    """

    def __init__(
        self,
        signoz_adapter: Optional[SigNozAdapter] = None,
        uptime_adapter: Optional[UptimeKumaAdapter] = None,
    ) -> None:
        self.signoz = signoz_adapter or SigNozAdapter()
        self.uptime = uptime_adapter or UptimeKumaAdapter()

    def get_summary(
        self,
        window_hours: float = 24.0,
        current_time: Optional[float] = None,
    ) -> ExecutiveKPISummary:
        """Calculates executive KPI summary over the specified window (default 24h)."""
        now = current_time if current_time is not None else time.time()
        window_seconds = window_hours * 3600.0
        cutoff = now - window_seconds

        # Aggregate spans
        spans = [s for s in self.signoz._spans if s.start_time >= cutoff]
        total_requests = len(spans)
        errors = sum(1 for s in spans if getattr(s.status, "value", str(s.status)) == "error")
        overall_error_rate = (errors / total_requests) if total_requests > 0 else 0.0

        durations = [s.duration_ms for s in spans if s.duration_ms > 0]
        avg_latency = (sum(durations) / len(durations)) if durations else 0.0

        # Aggregate metrics
        metrics = [m for m in self.signoz._metrics if m.timestamp >= cutoff]

        total_cost = 0.0
        total_tokens = 0
        tenant_spends: Dict[str, float] = {}
        tenant_requests: Dict[str, int] = {}
        model_costs: Dict[str, float] = {}
        active_tenants: Set[str] = set()
        active_users: Set[str] = set()

        for s in spans:
            t_id = s.attributes.get("tenant_id")
            if t_id:
                active_tenants.add(t_id)
                tenant_requests[t_id] = tenant_requests.get(t_id, 0) + 1
            u_id = s.attributes.get("user_id")
            if u_id:
                active_users.add(u_id)

        for m in metrics:
            t_id = m.labels.get("tenant_id")
            if t_id:
                active_tenants.add(t_id)
            u_id = m.labels.get("user_id")
            if u_id:
                active_users.add(u_id)

            model = m.labels.get("model", "general")

            if m.name == "llm.cost.usd":
                total_cost += m.value
                model_costs[model] = model_costs.get(model, 0.0) + m.value
                if t_id:
                    tenant_spends[t_id] = tenant_spends.get(t_id, 0.0) + m.value
            elif m.name == "llm.tokens.total":
                total_tokens += int(m.value)

        # Top tenants by spend
        top_tenants: List[Dict[str, Any]] = [
            {
                "tenant_id": tid,
                "spend_usd": round(cost, 4),
                "requests": tenant_requests.get(tid, 0),
            }
            for tid, cost in sorted(tenant_spends.items(), key=lambda x: x[1], reverse=True)
        ]

        # Calculate uptime percentage from Uptime Kuma if monitors exist
        uptime_pct = 99.99
        if hasattr(self.uptime, "_monitors") and self.uptime._monitors:
            up_count = sum(1 for m in self.uptime._monitors.values() if getattr(m, "active", True))
            uptime_pct = (up_count / len(self.uptime._monitors)) * 100.0

        return ExecutiveKPISummary(
            timestamp=now,
            time_window_hours=window_hours,
            total_cost_usd=round(total_cost, 4),
            total_tokens_consumed=total_tokens,
            total_requests=total_requests,
            active_tenants_count=len(active_tenants),
            active_users_count=len(active_users),
            uptime_percentage=round(uptime_pct, 2),
            top_tenants_by_spend=top_tenants[:10],
            model_cost_breakdown={k: round(v, 4) for k, v in model_costs.items()},
            average_system_latency_ms=round(avg_latency, 2),
            overall_error_rate=round(overall_error_rate, 4),
        )
