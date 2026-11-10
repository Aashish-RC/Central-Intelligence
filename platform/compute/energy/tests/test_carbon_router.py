"""Unit tests for CarbonEnergyRouter (Task 16.2)."""

import pytest
from platform.compute.energy.carbon_router import (
    CarbonEnergyRouter,
    RegionCarbonInfo,
    ScheduleDecision,
    WorkloadPriority,
)


@pytest.fixture
def router():
    # Set max batch carbon threshold to 150 gCO2/kWh
    return CarbonEnergyRouter(max_batch_carbon_threshold=150.0)


def test_realtime_request_executes_immediately(router: CarbonEnergyRouter):
    """Realtime interactive requests execute immediately regardless of carbon intensity."""
    decision = router.route_workload(
        task_id="chat_001",
        token_count=1500,
        priority=WorkloadPriority.REALTIME,
    )
    assert decision.execute_now is True
    assert decision.defer_seconds == 0.0
    assert decision.estimated_joules > 0.0
    assert decision.target_region == "eu-north-clean"


def test_batch_deferred_to_off_peak_when_carbon_intensity_high(router: CarbonEnergyRouter):
    """Acceptance test: Batch deferred to off-peak when carbon intensity is higher than threshold."""
    # Simulate both local and clean regions having temporarily high grid intensity (e.g. winter peak)
    router.set_region_metrics("eu-north-clean", intensity=250.0, is_off_peak=False)
    router.set_region_metrics("us-east-fossil", intensity=450.0, is_off_peak=False)

    decision = router.route_workload(
        task_id="batch_dataset_eval_002",
        token_count=1000000,  # 1M tokens heavy batch
        priority=WorkloadPriority.BATCH,
        preferred_region="us-east-fossil",
    )
    assert decision.execute_now is False
    assert decision.defer_seconds > 0.0
    assert "Deferred to off-peak" in decision.reason


def test_batch_rerouted_to_cleaner_renewable_region(router: CarbonEnergyRouter):
    """When preferred region is dirty, batch is rerouted to available clean region immediately."""
    # eu-north-clean is 35 gCO2/kWh (below 150), us-east-fossil is 420 gCO2/kWh
    decision = router.route_workload(
        task_id="batch_embedding_003",
        token_count=500000,
        priority=WorkloadPriority.BATCH,
        preferred_region="us-east-fossil",
    )
    assert decision.execute_now is True
    assert decision.target_region == "eu-north-clean"
    assert "re-routed to clean renewable region" in decision.reason


def test_energy_joules_tracking(router: CarbonEnergyRouter):
    """Tracker accurately estimates Joules per request based on token volume."""
    joules, carbon = router.estimate_energy_and_carbon(token_count=10000, region_id="eu-north-clean")
    # 10,000 tokens * 0.02 J/token = 200 Joules
    assert pytest.approx(joules, rel=1e-2) == 200.0
    assert carbon > 0.0
