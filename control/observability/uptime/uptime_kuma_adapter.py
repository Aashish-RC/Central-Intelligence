"""Uptime Kuma Health & Status Page Adapter (Layer 14: Features 14.13, 14.21).

Provides automated endpoint health monitoring, response ping latency checks,
threshold alert dispatching, and public component status page publishing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger("control.observability.uptime")


class ServiceStatus(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    MAINTENANCE = "maintenance"


@dataclass
class ServiceMonitor:
    monitor_id: str
    name: str
    url: str
    interval_seconds: int = 60
    status: ServiceStatus = ServiceStatus.OPERATIONAL
    last_ping_ms: float = 0.0
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    checks_count: int = 0
    failures_count: int = 0
    last_checked_at: Optional[float] = None
    alert_threshold_failures: int = 3


@dataclass
class IncidentReport:
    incident_id: str
    monitor_id: str
    title: str
    description: str
    severity: str  # 'minor', 'major', 'critical'
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None


class UptimeKumaAdapter:
    """Enterprise uptime monitoring & public status page engine."""

    def __init__(
        self,
        api_url: str = "http://localhost:3001",
        alert_webhook_url: Optional[str] = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.alert_webhook_url = alert_webhook_url

        self._monitors: Dict[str, ServiceMonitor] = [] if False else {}
        self._incidents: List[IncidentReport] = []
        self._alert_log: List[Dict[str, Any]] = []

    def add_monitor(
        self,
        name: str,
        url: str,
        interval_seconds: int = 60,
        alert_threshold_failures: int = 2,
    ) -> ServiceMonitor:
        """Registers a service endpoint for periodic health checks."""
        monitor_id = f"mon_{int(time.time()*1000)}_{len(self._monitors)}"
        monitor = ServiceMonitor(
            monitor_id=monitor_id,
            name=name,
            url=url,
            interval_seconds=interval_seconds,
            alert_threshold_failures=alert_threshold_failures,
        )
        self._monitors[monitor_id] = monitor
        return monitor

    def ping_monitor(
        self,
        monitor_id: str,
        custom_checker: Optional[Callable[[], Tuple[bool, float]]] = None,
    ) -> ServiceMonitor:
        """Performs a health check probe against the monitored service."""
        mon = self._monitors.get(monitor_id)
        if not mon:
            raise ValueError(f"Monitor '{monitor_id}' not found.")

        is_healthy = True
        ping_ms = 10.0

        if custom_checker:
            is_healthy, ping_ms = custom_checker()
        else:
            try:
                start = time.time()
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(mon.url)
                    ping_ms = (time.time() - start) * 1000.0
                    is_healthy = 200 <= resp.status_code < 400
            except Exception:
                is_healthy = False
                ping_ms = 0.0

        mon.checks_count += 1
        mon.last_checked_at = time.time()
        mon.last_ping_ms = round(ping_ms, 2)

        if is_healthy:
            mon.consecutive_failures = 0
            mon.status = ServiceStatus.OPERATIONAL
        else:
            mon.failures_count += 1
            mon.consecutive_failures += 1
            if mon.consecutive_failures >= mon.alert_threshold_failures:
                mon.status = ServiceStatus.OUTAGE
                self._dispatch_alert(mon, "Service Outage Detected")
            else:
                mon.status = ServiceStatus.DEGRADED

        # Calculate uptime %
        if mon.checks_count > 0:
            uptime = ((mon.checks_count - mon.failures_count) / mon.checks_count) * 100.0
            mon.uptime_percentage = round(uptime, 2)

        return mon

    def _dispatch_alert(self, monitor: ServiceMonitor, message: str) -> None:
        """Emits threshold alert for outage notification (14.13)."""
        alert = {
            "alert_id": str(uuid4()),
            "monitor_id": monitor.monitor_id,
            "service_name": monitor.name,
            "status": monitor.status.value,
            "consecutive_failures": monitor.consecutive_failures,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._alert_log.append(alert)

        # Create active incident
        self._incidents.append(
            IncidentReport(
                incident_id=f"inc_{int(time.time()*1000)}",
                monitor_id=monitor.monitor_id,
                title=f"{monitor.name} is down",
                description=f"Automated health check failed {monitor.consecutive_failures} times consecutively.",
                severity="critical",
            )
        )

    def get_status_page(self) -> Dict[str, Any]:
        """Publishes the public component health status page (14.21)."""
        monitors = list(self._monitors.values())
        if not monitors:
            overall = ServiceStatus.OPERATIONAL
        elif any(m.status == ServiceStatus.OUTAGE for m in monitors):
            overall = ServiceStatus.OUTAGE
        elif any(m.status == ServiceStatus.DEGRADED for m in monitors):
            overall = ServiceStatus.DEGRADED
        else:
            overall = ServiceStatus.OPERATIONAL

        active_incidents = [i for i in self._incidents if i.resolved_at is None]

        return {
            "system_status": overall.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "services": [
                {
                    "name": m.name,
                    "status": m.status.value,
                    "last_ping_ms": m.last_ping_ms,
                    "uptime_percentage": m.uptime_percentage,
                }
                for m in monitors
            ],
            "active_incidents": [
                {
                    "incident_id": inc.incident_id,
                    "title": inc.title,
                    "severity": inc.severity,
                    "started_at": inc.started_at,
                }
                for inc in active_incidents
            ],
        }

