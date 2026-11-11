"""Disaster Recovery and Cross-Region Failover (L16 Compute - Feature 16.20).

Monitors regional inference endpoints using ProviderHealthTracker, performs
health-check-based failover (e.g., US -> EU when US is down), supports manual
drain/maintenance mode, and enforces clean failback once recovery stabilizes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from platform_infra.compute.health.provider_health import (
    ProviderHealthTracker,
    ProviderStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class RegionEndpoint:
    """A regional compute deployment endpoint."""

    region_id: str
    endpoint_url: str
    priority: int = 1  # Lower integer = higher priority
    drained: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class FailoverDecision:
    """Result of selecting or failing over to a healthy regional endpoint."""

    selected_region: Optional[str]
    endpoint_url: Optional[str]
    failed_over_from: Optional[str] = None
    reason: str = "primary_healthy"
    timestamp: float = field(default_factory=time.time)


class RegionalFailoverManager:
    """Coordinates active-passive and active-active regional DR failover."""

    def __init__(
        self,
        health_tracker: Optional[ProviderHealthTracker] = None,
        failure_threshold: int = 2,
        recovery_threshold: int = 2,
    ) -> None:
        self.health_tracker = health_tracker or ProviderHealthTracker(
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
        )
        self._regions: Dict[str, RegionEndpoint] = {}
        self._active_region: Optional[str] = None
        self._history: List[FailoverDecision] = []

    def register_region(self, endpoint: RegionEndpoint) -> None:
        """Register a regional endpoint and promote it if none active yet."""
        self._regions[endpoint.region_id] = endpoint
        self.health_tracker.record_success(endpoint.region_id, latency_ms=10.0)
        if self._active_region is None:
            ordered = self._ordered_regions()
            self._active_region = ordered[0].region_id if ordered else endpoint.region_id

    def _ordered_regions(self) -> List[RegionEndpoint]:
        return sorted(self._regions.values(), key=lambda r: (r.priority, r.region_id))

    def is_region_available(self, region_id: str) -> bool:
        """A region is available if registered, not drained, and not DOWN."""
        ep = self._regions.get(region_id)
        if ep is None or ep.drained:
            return False
        report = self.health_tracker.get_report(region_id)
        return report.status not in (ProviderStatus.DOWN, ProviderStatus.RATE_LIMITED)

    def record_health_check(
        self,
        region_id: str,
        healthy: bool,
        latency_ms: float = 50.0,
        error: str = "health_check_failed",
    ) -> FailoverDecision:
        """Record a regional health probe and trigger failover if current active goes DOWN."""
        if region_id not in self._regions:
            raise KeyError(f"Unknown region: {region_id}")

        previous_active = self._active_region
        if healthy:
            self.health_tracker.record_success(region_id, latency_ms=latency_ms)
        else:
            self.health_tracker.record_failure(region_id, error_message=error)

        return self.evaluate_active_region(previous_active=previous_active)

    def drain_region(self, region_id: str, drained: bool = True) -> FailoverDecision:
        """Manually drain or un-drain a region for planned maintenance."""
        if region_id not in self._regions:
            raise KeyError(f"Unknown region: {region_id}")
        previous = self._active_region
        self._regions[region_id].drained = drained
        return self.evaluate_active_region(previous_active=previous)

    def evaluate_active_region(
        self,
        previous_active: Optional[str] = None,
        prefer_failback: bool = False,
    ) -> FailoverDecision:
        """Select the highest-priority available region, failing over if needed."""
        ordered = self._ordered_regions()
        available = [r for r in ordered if self.is_region_available(r.region_id)]

        if not available:
            decision = FailoverDecision(
                selected_region=None,
                endpoint_url=None,
                failed_over_from=previous_active or self._active_region,
                reason="all_regions_unavailable",
            )
            self._active_region = None
            self._history.append(decision)
            return decision

        current = self._active_region
        if not prefer_failback and current and self.is_region_available(current):
            ep = self._regions[current]
            return FailoverDecision(selected_region=current, endpoint_url=ep.endpoint_url, reason="active_healthy")

        target = available[0]
        failed_from = previous_active if (previous_active and previous_active != target.region_id) else (
            current if (current and current != target.region_id) else None
        )
        reason = "failback_to_primary" if (prefer_failback and failed_from) else (
            f"failover_from_{failed_from}" if failed_from else "primary_healthy"
        )
        self._active_region = target.region_id
        decision = FailoverDecision(
            selected_region=target.region_id,
            endpoint_url=target.endpoint_url,
            failed_over_from=failed_from,
            reason=reason,
        )
        if failed_from:
            logger.warning("Regional failover: %s -> %s (%s)", failed_from, target.region_id, reason)
            self._history.append(decision)
        return decision

    def get_active_region(self) -> Optional[RegionEndpoint]:
        if self._active_region is None:
            return None
        return self._regions.get(self._active_region)

    def get_failover_history(self) -> List[FailoverDecision]:
        return list(self._history)

