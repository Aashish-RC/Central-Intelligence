"""Resource Monitoring Agent: Autonomous agent tracking device load, RAM/CPU thresholds, and active task queues."""

import time
from typing import Callable, Optional
from ..core.interfaces import BaseInternalAgent, BaseVisibleLogStore
from ..core.models import (
    AgentLogEntry,
    AgentRunReport,
    AgentSeverity,
    AgentType,
    ResourceMetric,
    utc_now,
)


class ResourceMonitorAgent(BaseInternalAgent):
    """Monitors device compute resources, memory consumption, and issues throttle recommendations."""

    def __init__(
        self,
        visible_store: BaseVisibleLogStore,
        sampler_fn: Optional[Callable[[], ResourceMetric]] = None,
        cpu_threshold_percent: float = 90.0,
        ram_threshold_percent: float = 95.0,
    ):
        self.visible_store = visible_store
        self.sampler_fn = sampler_fn or self._default_sampler
        self.cpu_threshold_percent = cpu_threshold_percent
        self.ram_threshold_percent = ram_threshold_percent

    @property
    def agent_type(self) -> AgentType:
        return AgentType.RESOURCE_MONITOR

    def _default_sampler(self) -> ResourceMetric:
        # Standard fallback sampler without external dependencies
        return ResourceMetric(
            cpu_percent=15.0,
            ram_used_mb=1024.0,
            ram_percent=25.0,
            active_tasks=1,
            recorded_at=utc_now(),
        )

    def sample_metrics(self) -> ResourceMetric:
        return self.sampler_fn()

    def run_cycle(self) -> AgentRunReport:
        start_time = time.perf_counter()
        metric = self.sample_metrics()
        anomalies = 0

        # Check CPU warning
        if metric.cpu_percent > self.cpu_threshold_percent:
            anomalies += 1
            self.visible_store.append_log(
                AgentLogEntry(
                    agent_type=self.agent_type,
                    severity=AgentSeverity.WARNING,
                    action="cpu_threshold_exceeded",
                    message=f"CPU load is elevated at {metric.cpu_percent:.1f}% (Threshold: {self.cpu_threshold_percent:.1f}%)",
                    metadata={"cpu_percent": metric.cpu_percent},
                )
            )

        # Check RAM warning
        if metric.ram_percent > self.ram_threshold_percent:
            anomalies += 1
            self.visible_store.append_log(
                AgentLogEntry(
                    agent_type=self.agent_type,
                    severity=AgentSeverity.WARNING,
                    action="ram_threshold_exceeded",
                    message=f"RAM consumption is critical at {metric.ram_percent:.1f}% ({metric.ram_used_mb:.1f}MB used)",
                    metadata={"ram_percent": metric.ram_percent, "ram_used_mb": metric.ram_used_mb},
                )
            )

        # Log routine telemetry snapshot
        self.visible_store.append_log(
            AgentLogEntry(
                agent_type=self.agent_type,
                severity=AgentSeverity.INFO,
                action="telemetry_sample",
                message=f"Resource snapshot: CPU {metric.cpu_percent:.1f}% | RAM {metric.ram_percent:.1f}% | Active Tasks: {metric.active_tasks}",
                metadata={
                    "cpu_percent": metric.cpu_percent,
                    "ram_percent": metric.ram_percent,
                    "ram_used_mb": metric.ram_used_mb,
                    "active_tasks": metric.active_tasks,
                },
            )
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        summary = f"Sampled device metrics. Anomalies: {anomalies}."
        return AgentRunReport(
            agent_type=self.agent_type,
            success=True,
            items_processed=1,
            anomalies_detected=anomalies,
            duration_ms=round(duration_ms, 2),
            summary=summary,
        )
