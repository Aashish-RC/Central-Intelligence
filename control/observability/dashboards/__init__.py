"""
Observability Dashboards (Layer 14: Features 14.15, 14.16, 14.17, 14.18).

Provides:
- 14.15: Real-time System Dashboard (cluster-wide throughput, latency, errors)
- 14.16: Per-Tenant Dashboard (tenant-isolated metrics)
- 14.17: Per-App Dashboard (application-specific telemetry)
- 14.18: Executive Dashboard (high-level KPIs, cost, usage trends)
"""

from control.observability.dashboards.executive_dashboard import (
    ExecutiveDashboard,
    ExecutiveKPISummary,
)
from control.observability.dashboards.per_app_dashboard import (
    AppMetricsSummary,
    PerAppDashboard,
)
from control.observability.dashboards.per_tenant_dashboard import (
    PerTenantDashboard,
    TenantMetricsSummary,
)
from control.observability.dashboards.realtime_dashboard import (
    RealtimeDashboard,
    SystemRealtimeMetrics,
)

__all__ = [
    "RealtimeDashboard",
    "SystemRealtimeMetrics",
    "PerTenantDashboard",
    "TenantMetricsSummary",
    "PerAppDashboard",
    "AppMetricsSummary",
    "ExecutiveDashboard",
    "ExecutiveKPISummary",
]
