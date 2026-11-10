"""
Per-Tenant Observability Dashboard (Layer 14: Feature 14.16).

Provides strictly isolated telemetry views for multi-tenant deployments.
Guarantees tenant isolation: each tenant can only inspect metrics belonging to their tenant_id.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control.observability.signoz.signoz_adapter import SigNozAdapter

logger = logging.getLogger("control.observability.dashboards.per_tenant")


@dataclass
class TenantMetricsSummary:
    """Telemetry metrics isolated to a single tenant."""
    tenant_id: str
    request_count: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    average_latency_ms: float
    error_count: int
    error_rate: float
    models_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class PerTenantDashboard:
    """
    Per-tenant observability dashboard (Feature 14.16).
    Enforces strict tenant boundary isolation.
    """

    def __init__(self, signoz_adapter: Optional[SigNozAdapter] = None) -> None:
        self.signoz = signoz_adapter or SigNozAdapter()

    def get_tenant_metrics(
        self,
        target_tenant_id: str,
        requesting_tenant_id: str,
        is_admin: bool = False,
        window_seconds: float = 86400.0,
        current_time: Optional[float] = None,
    ) -> TenantMetricsSummary:
        """
        Retrieves metrics for target_tenant_id.
        Enforces tenant isolation: if requesting_tenant_id != target_tenant_id and not is_admin -> raise PermissionError.
        """
        if requesting_tenant_id != target_tenant_id and not is_admin:
            raise PermissionError(
                f"Tenant isolation violation: tenant '{requesting_tenant_id}' cannot view metrics for '{target_tenant_id}'."
            )

        now = current_time if current_time is not None else time.time()
        cutoff = now - window_seconds

        # Filter spans for target tenant
        tenant_spans = [
            s for s in self.signoz._spans
            if s.start_time >= cutoff and s.attributes.get("tenant_id") == target_tenant_id
        ]
        request_count = len(tenant_spans)
        errors = sum(1 for s in tenant_spans if getattr(s.status, "value", str(s.status)) == "error")
        error_rate = (errors / request_count) if request_count > 0 else 0.0

        durations = [s.duration_ms for s in tenant_spans if s.duration_ms > 0]
        avg_latency = (sum(durations) / len(durations)) if durations else 0.0

        # Filter metrics with matching label
        tenant_metrics = [
            m for m in self.signoz._metrics
            if m.timestamp >= cutoff and m.labels.get("tenant_id") == target_tenant_id
        ]

        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        total_cost = 0.0
        models_breakdown: Dict[str, Dict[str, Any]] = {}

        for m in tenant_metrics:
            model = m.labels.get("model", "unknown")
            if model not in models_breakdown:
                models_breakdown[model] = {"tokens": 0, "cost_usd": 0.0, "requests": 0}

            if m.name == "llm.tokens.total":
                total_tokens += int(m.value)
                models_breakdown[model]["tokens"] += int(m.value)
            elif m.name == "llm.tokens.prompt":
                prompt_tokens += int(m.value)
            elif m.name == "llm.tokens.completion":
                completion_tokens += int(m.value)
            elif m.name == "llm.cost.usd":
                total_cost += float(m.value)
                models_breakdown[model]["cost_usd"] += float(m.value)

        return TenantMetricsSummary(
            tenant_id=target_tenant_id,
            request_count=request_count,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=round(total_cost, 4),
            average_latency_ms=round(avg_latency, 2),
            error_count=errors,
            error_rate=round(error_rate, 4),
            models_breakdown=models_breakdown,
        )
