"""Carbon & Energy Router (L16 Compute - Task 16.28).

Tracks electrical energy expenditure (Joules per request) and regional
carbon emissions intensity (gCO2eq/kWh). Optimizes batch and asynchronous
inference tasks by dynamically routing to renewable energy regions or
deferring heavy batch runs to off-peak periods when grid carbon intensity is lowest.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkloadPriority(str, Enum):
    REALTIME = "realtime"
    BATCH = "batch"
    BACKGROUND = "background"


@dataclass
class RegionCarbonInfo:
    """Carbon intensity metrics for a compute data center region."""
    region_id: str
    name: str
    carbon_intensity_g_kwh: float  # grams CO2eq per kWh
    renewable_fraction: float = 0.5  # 0.0 to 1.0
    is_off_peak: bool = False
    average_joules_per_token: float = 0.02


@dataclass
class ScheduleDecision:
    """Decision produced by the carbon and energy router."""
    execute_now: bool
    target_region: str
    estimated_joules: float
    estimated_carbon_grams: float
    defer_seconds: float = 0.0
    reason: str = "Immediate execution permitted"


class CarbonEnergyRouter:
    """Routes compute workloads to optimize carbon efficiency and energy consumption."""

    def __init__(self, max_batch_carbon_threshold: float = 200.0) -> None:
        self.max_batch_carbon_threshold = max_batch_carbon_threshold
        self._regions: Dict[str, RegionCarbonInfo] = {
            "eu-north-clean": RegionCarbonInfo(
                region_id="eu-north-clean",
                name="Nordic Hydro/Wind DC",
                carbon_intensity_g_kwh=35.0,
                renewable_fraction=0.95,
                is_off_peak=True,
            ),
            "us-west-mixed": RegionCarbonInfo(
                region_id="us-west-mixed",
                name="Oregon Hydro/Gas Mix",
                carbon_intensity_g_kwh=180.0,
                renewable_fraction=0.60,
                is_off_peak=False,
            ),
            "us-east-fossil": RegionCarbonInfo(
                region_id="us-east-fossil",
                name="Virginia Grid Mix",
                carbon_intensity_g_kwh=420.0,
                renewable_fraction=0.25,
                is_off_peak=False,
            ),
        }
        self._execution_history: List[Dict[str, Any]] = []

    def set_region_metrics(self, region_id: str, intensity: float, is_off_peak: bool) -> None:
        """Update live telemetry for a region."""
        if region_id in self._regions:
            self._regions[region_id].carbon_intensity_g_kwh = intensity
            self._regions[region_id].is_off_peak = is_off_peak

    def get_cleanest_region(self) -> RegionCarbonInfo:
        """Return the region with lowest current carbon intensity."""
        return min(self._regions.values(), key=lambda r: r.carbon_intensity_g_kwh)

    def estimate_energy_and_carbon(
        self,
        token_count: int,
        region_id: str,
    ) -> tuple[float, float]:
        """Estimate Joules consumed and equivalent grams of CO2."""
        region = self._regions.get(region_id) or self.get_cleanest_region()
        # Joules = token_count * J_per_token
        joules = token_count * region.average_joules_per_token
        # 1 kWh = 3,600,000 Joules
        kwh = joules / 3_600_000.0
        carbon_grams = kwh * region.carbon_intensity_g_kwh
        return joules, carbon_grams

    def route_workload(
        self,
        task_id: str,
        token_count: int,
        priority: WorkloadPriority = WorkloadPriority.REALTIME,
        preferred_region: Optional[str] = None,
        max_acceptable_delay_seconds: float = 3600.0,
    ) -> ScheduleDecision:
        """Determine routing and schedule decision for an inference workload."""
        cleanest = self.get_cleanest_region()
        default_region = self._regions.get(preferred_region or "us-east-fossil") or cleanest

        # 1. Realtime tasks must execute immediately with lowest carbon region available
        if priority == WorkloadPriority.REALTIME:
            joules, carbon = self.estimate_energy_and_carbon(token_count, cleanest.region_id)
            decision = ScheduleDecision(
                execute_now=True,
                target_region=cleanest.region_id,
                estimated_joules=joules,
                estimated_carbon_grams=carbon,
                defer_seconds=0.0,
                reason="Realtime priority: dispatched immediately to cleanest available region",
            )
            self._record(task_id, decision, priority)
            return decision

        # 2. Batch workloads: Check if regional carbon intensity is too high
        current_region_info = default_region
        joules, current_carbon = self.estimate_energy_and_carbon(token_count, current_region_info.region_id)

        if current_region_info.carbon_intensity_g_kwh > self.max_batch_carbon_threshold and not current_region_info.is_off_peak:
            # Check if cleanest region can run it immediately within budget
            clean_joules, clean_carbon = self.estimate_energy_and_carbon(token_count, cleanest.region_id)
            if cleanest.carbon_intensity_g_kwh <= self.max_batch_carbon_threshold:
                decision = ScheduleDecision(
                    execute_now=True,
                    target_region=cleanest.region_id,
                    estimated_joules=clean_joules,
                    estimated_carbon_grams=clean_carbon,
                    defer_seconds=0.0,
                    reason=f"Batch re-routed to clean renewable region '{cleanest.name}'",
                )
            else:
                # Both regions exceed threshold, defer batch to off-peak hours
                defer_time = min(14400.0, max_acceptable_delay_seconds)  # e.g., 4 hours until off-peak
                decision = ScheduleDecision(
                    execute_now=False,
                    target_region=cleanest.region_id,
                    estimated_joules=clean_joules,
                    estimated_carbon_grams=clean_carbon,
                    defer_seconds=defer_time,
                    reason=f"High carbon intensity ({current_region_info.carbon_intensity_g_kwh:.1f} gCO2/kWh). Deferred to off-peak.",
                )
        else:
            decision = ScheduleDecision(
                execute_now=True,
                target_region=current_region_info.region_id,
                estimated_joules=joules,
                estimated_carbon_grams=current_carbon,
                defer_seconds=0.0,
                reason="Carbon intensity acceptable or currently off-peak.",
            )

        self._record(task_id, decision, priority)
        return decision

    def _record(self, task_id: str, decision: ScheduleDecision, priority: WorkloadPriority) -> None:
        self._execution_history.append({
            "task_id": task_id,
            "decision": decision,
            "priority": priority.value,
            "timestamp": time.time(),
        })

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._execution_history)

