"""
Tests for BYO Infrastructure Compute Metering (Feature 13.08).
"""

import pytest

from control.billing.byoi.infrastructure_meter import (
    BYOInfrastructureMeter,
    ComputeTargetType,
)
from control.billing.metering.openmeter_adapter import OpenMeterAdapter


def test_tracks_fifty_percent_local_thirty_percent_other_device_twenty_percent_cloud():
    """
    Acceptance criterion: Can track "50% local, 30% other device, 20% cloud".
    """
    meter = BYOInfrastructureMeter()
    user_id = "user_dist_50_30_20"

    # Total 10,000 tokens:
    # 5,000 local (50%)
    # 3,000 peer device (30%)
    # 2,000 cloud (20%)

    # 1. 50% Local compute (e.g. on MacBook Pro M3)
    meter.record_compute(
        user_id=user_id,
        compute_target=ComputeTargetType.LOCAL,
        tokens=5000,
        target_identifier="local_macbook_m3",
        duration_ms=450.0,
    )

    # 2. 30% Peer device / other device (e.g. Desktop RTX 4090 on home LAN)
    meter.record_compute(
        user_id=user_id,
        compute_target=ComputeTargetType.PEER_DEVICE,
        tokens=3000,
        target_identifier="peer_desktop_rtx4090",
        duration_ms=280.0,
    )

    # 3. 20% Cloud compute (e.g. AWS Bedrock / Lambda)
    meter.record_compute(
        user_id=user_id,
        compute_target=ComputeTargetType.CLOUD,
        tokens=2000,
        target_identifier="cloud_aws_us_east_1",
        duration_ms=190.0,
    )

    distribution = meter.get_distribution(user_id)

    assert distribution.total_tokens == 10000
    assert distribution.total_invocations == 3

    # Exact percentage assertions verifying acceptance condition
    assert distribution.by_target_percentage["local"] == 50.0
    assert distribution.by_target_percentage["peer_device"] == 30.0
    assert distribution.by_target_percentage["cloud"] == 20.0

    assert distribution.by_target_tokens["local"] == 5000
    assert distribution.by_target_tokens["peer_device"] == 3000
    assert distribution.by_target_tokens["cloud"] == 2000


def test_openmeter_mirroring():
    openmeter = OpenMeterAdapter()
    meter = BYOInfrastructureMeter(openmeter_adapter=openmeter)
    user_id = "user_openmeter_mirror"

    meter.record_compute(
        user_id=user_id,
        compute_target="local",
        tokens=1200,
        target_identifier="ollama_mac",
    )

    assert len(openmeter._local_events) == 1
    event = openmeter._local_events[0]
    assert event.user_id == user_id
    assert event.compute_provider == "local"
    assert event.total_tokens == 1200


def test_empty_user_distribution():
    meter = BYOInfrastructureMeter()
    dist = meter.get_distribution("user_non_existent")
    assert dist.total_tokens == 0
    assert dist.by_target_percentage["local"] == 0.0
    assert dist.by_target_percentage["peer_device"] == 0.0
    assert dist.by_target_percentage["cloud"] == 0.0
