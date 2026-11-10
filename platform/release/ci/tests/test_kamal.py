"""Unit tests for KamalAdapter (Task 17.2)."""

import pytest
from platform.release.ci.kamal_adapter import (
    KamalAdapter,
    KamalConfig,
    DeploymentPhase,
)


@pytest.fixture
def kamal():
    config = KamalConfig(
        service_name="central-api",
        servers=["10.0.0.1", "10.0.0.2"],
        healthcheck_path="/healthz",
    )
    return KamalAdapter(config=config)


def test_zero_downtime_ci_deploy(kamal: KamalAdapter):
    """Acceptance test: Can deploy from CI with zero downtime."""
    target_tag = "release-v2.5.0"

    deployment = kamal.deploy(version_tag=target_tag)

    assert deployment.phase == DeploymentPhase.COMPLETED
    assert deployment.zero_downtime_guaranteed is True
    assert deployment.downtime_seconds == 0.0

    # Ensure proxy swap was executed only after healthy boot
    phases = deployment.phases_completed
    assert "boot_container" in phases
    assert "healthcheck_probe" in phases
    assert "proxy_swap" in phases
    assert phases.index("healthcheck_probe") < phases.index("proxy_swap")
    assert phases.index("proxy_swap") < phases.index("stop_old_container")

    # Verify all servers running new version
    active = kamal.get_active_versions()
    assert active["10.0.0.1"] == target_tag
    assert active["10.0.0.2"] == target_tag
