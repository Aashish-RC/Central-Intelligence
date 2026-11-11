"""Tests for cross-region failover & DR manager."""

from platform_infra.compute.resilience.failover import (
    RegionEndpoint,
    RegionalFailoverManager,
)


def test_us_to_eu_failover_and_recovery():
    mgr = RegionalFailoverManager(failure_threshold=2, recovery_threshold=2)
    mgr.register_region(RegionEndpoint(region_id="us-east-1", endpoint_url="https://us.infer.local", priority=1))
    mgr.register_region(RegionEndpoint(region_id="eu-west-1", endpoint_url="https://eu.infer.local", priority=2))

    assert mgr.get_active_region().region_id == "us-east-1"

    # Trigger failures on us-east-1
    mgr.record_health_check("us-east-1", healthy=False, error="timeout")
    decision = mgr.record_health_check("us-east-1", healthy=False, error="503")

    assert decision.selected_region == "eu-west-1"
    assert decision.failed_over_from == "us-east-1"
    assert len(mgr.get_failover_history()) == 1

    # Recover us-east-1 and failback explicitly
    mgr.record_health_check("us-east-1", healthy=True)
    mgr.record_health_check("us-east-1", healthy=True)
    failback = mgr.evaluate_active_region(prefer_failback=True)
    assert failback.selected_region == "us-east-1"


def test_drain_triggers_failover_and_all_down_returns_none():
    mgr = RegionalFailoverManager(failure_threshold=1)
    mgr.register_region(RegionEndpoint(region_id="us-east-1", endpoint_url="https://us.local", priority=1))
    mgr.register_region(RegionEndpoint(region_id="eu-west-1", endpoint_url="https://eu.local", priority=2))

    d1 = mgr.drain_region("us-east-1", drained=True)
    assert d1.selected_region == "eu-west-1"

    d2 = mgr.record_health_check("eu-west-1", healthy=False)
    assert d2.selected_region is None
    assert d2.reason == "all_regions_unavailable"

