"""Integration tests for KamalAdapter live CLI execution (Milestone 4 - Task 4.1)."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from control.safety.production_guard import ProductionSafetyError
from platform_infra.release.ci.kamal_adapter import (
    DeploymentPhase,
    KamalAdapter,
    KamalConfig,
)


@pytest.fixture(autouse=True)
def setup_live_env(monkeypatch):
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("KAMAL_LIVE") != "1", reason="Requires KAMAL_LIVE=1")
def test_kamal_not_installed_fails_closed(monkeypatch):
    """When kamal binary is absent from PATH in live mode, deploy() raises ProductionSafetyError."""
    monkeypatch.setattr("shutil.which", lambda cmd: None if cmd == "kamal" else "/usr/bin/which")
    adapter = KamalAdapter()
    assert adapter.adapter_mode == "live"

    with pytest.raises(ProductionSafetyError) as exc_info:
        adapter.deploy(version_tag="v1.0.0")

    assert "kamal CLI not found on PATH" in str(exc_info.value)


@pytest.mark.live
@pytest.mark.skipif(os.getenv("KAMAL_LIVE") != "1", reason="Requires KAMAL_LIVE=1")
def test_kamal_cli_invoked_on_deploy(monkeypatch):
    """Verifies that all 6 kamal CLI subcommands are invoked in expected order on deploy."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/local/bin/kamal")

    executed_commands = []

    def fake_run(cmd, capture_output=True, text=True, env=None, timeout=600, check=True):
        executed_commands.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    # Mock healthcheck probe so it succeeds immediately
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("httpx.get", lambda url, timeout=1.0: mock_resp)

    config = KamalConfig(
        service_name="central-intelligence-api",
        servers=["192.168.1.101"],
        healthcheck_path="/healthz",
    )
    adapter = KamalAdapter(config=config)
    deployment = adapter.deploy(version_tag="v2.0.0")

    assert deployment.phase == DeploymentPhase.COMPLETED
    assert deployment.zero_downtime_guaranteed is True

    expected_commands = [
        ["kamal", "lock", "acquire"],
        ["kamal", "registry", "push"],
        ["kamal", "app", "boot", "--version", "v2.0.0"],
        ["kamal", "proxy", "boot"],
        ["kamal", "app", "stop", "--version", "previous"],
        ["kamal", "lock", "release"],
    ]
    assert executed_commands == expected_commands
    assert adapter.get_active_versions()["192.168.1.101"] == "v2.0.0"


@pytest.mark.live
@pytest.mark.skipif(os.getenv("KAMAL_LIVE") != "1", reason="Requires KAMAL_LIVE=1")
def test_healthcheck_failure_propagates(monkeypatch):
    """When healthcheck probe times out in live mode, deploy() raises ProductionSafetyError and marks phase FAILED."""
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/local/bin/kamal")

    def fake_run(cmd, capture_output=True, text=True, env=None, timeout=600, check=True):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    # Healthcheck always returns 500 or raises
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    monkeypatch.setattr("httpx.get", lambda url, timeout=1.0: mock_resp)

    config = KamalConfig(
        service_name="central-intelligence-api",
        servers=["192.168.1.101"],
        healthcheck_path="/healthz",
        healthcheck_timeout_s=0.2,
        healthcheck_interval_s=0.05,
    )
    adapter = KamalAdapter(config=config)

    with pytest.raises(ProductionSafetyError) as exc_info:
        adapter.deploy(version_tag="v2.0.0")

    assert "did not return 200 within" in str(exc_info.value)
    # Check the deployment is recorded and failed
    assert len(adapter._deployments) == 1
    dep = list(adapter._deployments.values())[0]
    assert dep.phase == DeploymentPhase.FAILED
