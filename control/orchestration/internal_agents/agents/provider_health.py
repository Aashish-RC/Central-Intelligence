"""Provider Health Agent: Autonomous background agent monitoring LLM provider availability and latency."""

import time
from typing import Callable, Dict, List, Optional
from ..core.interfaces import BaseInternalAgent, BaseVisibleLogStore
from ..core.models import (
    AgentLogEntry,
    AgentRunReport,
    AgentSeverity,
    AgentType,
    HealthCheckResult,
    utc_now,
)


class ProviderHealthAgent(BaseInternalAgent):
    """Monitors provider health, tracks p95 latencies, and signals failovers when endpoints degrade."""

    def __init__(
        self,
        visible_store: BaseVisibleLogStore,
        providers: Optional[Dict[str, Callable[[], float]]] = None,
        latency_threshold_ms: float = 3000.0,
    ):
        self.visible_store = visible_store
        # Mapping: provider_name -> ping_func returning latency_ms or raising Exception
        self.providers = providers or {}
        self.latency_threshold_ms = latency_threshold_ms

    @property
    def agent_type(self) -> AgentType:
        return AgentType.PROVIDER_HEALTH

    def register_provider(self, name: str, ping_fn: Callable[[], float]) -> None:
        self.providers[name] = ping_fn

    def check_provider(self, name: str) -> HealthCheckResult:
        ping_fn = self.providers.get(name)
        if not ping_fn:
            return HealthCheckResult(
                provider=name,
                is_healthy=False,
                error_message="Provider ping function not registered",
                checked_at=utc_now(),
            )

        start = time.perf_counter()
        try:
            latency_ms = ping_fn()
            is_healthy = latency_ms <= self.latency_threshold_ms
            err = None if is_healthy else f"Latency ({latency_ms:.1f}ms) exceeded threshold ({self.latency_threshold_ms:.1f}ms)"
            return HealthCheckResult(
                provider=name,
                is_healthy=is_healthy,
                latency_ms=round(latency_ms, 2),
                error_message=err,
                checked_at=utc_now(),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return HealthCheckResult(
                provider=name,
                is_healthy=False,
                latency_ms=round(elapsed_ms, 2),
                error_message=str(e),
                checked_at=utc_now(),
            )

    def run_cycle(self) -> AgentRunReport:
        start_time = time.perf_counter()
        results: List[HealthCheckResult] = []
        anomalies = 0

        for name in list(self.providers.keys()):
            res = self.check_provider(name)
            results.append(res)

            severity = AgentSeverity.INFO if res.is_healthy else AgentSeverity.WARNING
            if not res.is_healthy:
                anomalies += 1

            self.visible_store.append_log(
                AgentLogEntry(
                    agent_type=self.agent_type,
                    severity=severity,
                    action="provider_ping",
                    message=f"Provider '{name}' health check: {'HEALTHY' if res.is_healthy else 'DEGRADED'} ({res.latency_ms}ms)",
                    metadata={
                        "provider": name,
                        "latency_ms": res.latency_ms,
                        "is_healthy": res.is_healthy,
                        "error": res.error_message,
                    },
                )
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        summary = f"Checked {len(results)} providers; {anomalies} anomalies detected."
        return AgentRunReport(
            agent_type=self.agent_type,
            success=True,
            items_processed=len(results),
            anomalies_detected=anomalies,
            duration_ms=round(duration_ms, 2),
            summary=summary,
        )
