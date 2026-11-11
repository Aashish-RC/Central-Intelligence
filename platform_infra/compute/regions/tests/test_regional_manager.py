"""Tests for regional serving, residency enforcement, and traffic distribution."""

import pytest

from platform_infra.compute.regions.regional_manager import (
    RegionNode,
    RegionalServingManager,
    ResidencyViolationError,
    RoutingRequest,
)


def _build_manager() -> RegionalServingManager:
    mgr = RegionalServingManager()
    mgr.register_node(
        RegionNode(
            region_id="eu-central-1",
            residency_zone="EU",
            endpoint_url="https://eu.api.local",
            latitude=50.11,
            longitude=8.68,
            weight=1.0,
            capacity_rps=100,
        )
    )
    mgr.register_node(
        RegionNode(
            region_id="us-east-1",
            residency_zone="US",
            endpoint_url="https://us.api.local",
            latitude=39.04,
            longitude=-77.49,
            weight=2.0,
            capacity_rps=200,
        )
    )
    return mgr


def test_eu_user_routes_to_eu_and_residency_enforced():
    mgr = _build_manager()
    # User in Berlin with EU residency
    decision = mgr.route(
        RoutingRequest(
            request_id="r1",
            model_id="llama-3.1",
            user_latitude=52.52,
            user_longitude=13.40,
            required_residency="EU",
        )
    )
    assert decision.region_id == "eu-central-1"
    assert decision.residency_zone == "EU"

    # If EU goes down, EU-resident request must fail closed rather than leaking to US
    mgr.set_health("eu-central-1", False)
    with pytest.raises(ResidencyViolationError):
        mgr.route(
            RoutingRequest(
                request_id="r2",
                model_id="llama-3.1",
                user_latitude=52.52,
                user_longitude=13.40,
                required_residency="EU",
            )
        )


def test_weighted_traffic_distribution():
    mgr = _build_manager()
    dist = mgr.distribute_traffic(total_requests=100)
    assert sum(dist.values()) == 100
    assert dist["us-east-1"] > dist["eu-central-1"]

