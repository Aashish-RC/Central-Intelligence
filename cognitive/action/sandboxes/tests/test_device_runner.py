"""Unit tests for DeviceRunner: Code runs without escaping its limits."""

import os
import pytest
from sandboxes.core.models import ResourceLimits, SandboxStatus
from sandboxes.runner.device_runner import DeviceRunner
from sandboxes.trusted_host import TrustedExecutionContext


@pytest.fixture
def trusted_ctx(monkeypatch):
    monkeypatch.setenv("CENTRAL_TRUSTED_HOST_TOKEN", "device-test-token")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")
    return TrustedExecutionContext(
        caller_id="orchestrator",
        auth_token="device-test-token",
        capability="TEST_FIXTURE_EXECUTION",
        purpose="device-runner-tests",
    )


@pytest.fixture
def device_runner(trusted_ctx):
    return DeviceRunner(trusted_context=trusted_ctx)


def test_code_runs_without_escaping_limits(device_runner, tmp_path):
    """Core verification: Authorized code runs cleanly and captures output without escaping limits."""
    code = """
import sys
values = [x * 2 for x in range(5)]
print(f"COMPUTED: {values}")
"""
    result = device_runner.run_python(code, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert "COMPUTED: [0, 2, 4, 6, 8]" in result.stdout
    assert result.duration_ms >= 0


def test_code_runtime_error_captured(device_runner, tmp_path):
    code = "raise ZeroDivisionError('Intentional Sandbox Exception')"
    result = device_runner.run_python(code, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.FAILED
    assert result.exit_code != 0
    assert "ZeroDivisionError" in result.stderr


def test_shell_command_execution(device_runner, tmp_path):
    result = device_runner.run_shell("echo SandboxedShellOutput", scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert "SandboxedShellOutput" in result.stdout


def test_blocked_code_does_not_execute(device_runner, tmp_path):
    # Attempt prohibited library
    blocked_code = "import ctypes\nprint('Should not run')"
    result = device_runner.run_python(blocked_code, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.BLOCKED
    assert "ctypes" in result.stderr
    assert "Should not run" not in result.stdout


def test_untrusted_device_runner_blocked_without_context(tmp_path):
    """DeviceRunner without trusted context strictly blocks untrusted execution."""
    untrusted_runner = DeviceRunner()
    result = untrusted_runner.run_shell("echo should_not_run", scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.BLOCKED
    assert result.exit_code == -1
    assert "Untrusted command execution on the host machine is strictly prohibited" in result.stderr


def test_device_runner_strictly_prohibited_in_production(tmp_path, trusted_ctx, monkeypatch):
    """DeviceRunner unconditionally blocks host execution in production even with trusted context."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    runner = DeviceRunner(trusted_context=trusted_ctx)
    result = runner.run_shell("echo should_not_run", scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.BLOCKED
    assert result.exit_code == -1
    assert "strictly forbidden in production" in result.stderr
