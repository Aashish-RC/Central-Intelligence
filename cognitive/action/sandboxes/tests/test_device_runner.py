"""Unit tests for DeviceRunner: Code runs without escaping its limits."""

import pytest
from sandboxes.core.models import ResourceLimits, SandboxStatus
from sandboxes.runner.device_runner import DeviceRunner


@pytest.fixture
def device_runner():
    return DeviceRunner()


def test_code_runs_without_escaping_limits(device_runner, tmp_path):
    """Core verification: Code runs cleanly and captures output without escaping limits."""
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
