"""Unit tests (fake command runner) and live tests for DockerRunner."""

import os
import subprocess
from typing import Any, List
import pytest

from sandboxes.core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
)
from sandboxes.governor.security_governor import SecurityGovernor
from sandboxes.manager import SandboxManager
from sandboxes.runner.docker_runner import DockerRunner
from sandboxes.runner.local_process_runner import LocalProcessRunner


# ==============================================================================
# Unit Tests (Fake Command Runner)
# ==============================================================================

def test_docker_runner_cli_structure():
    """Verify that DockerRunner constructs the exact requested docker CLI arguments."""
    captured_commands: List[List[str]] = []
    captured_inputs: List[str] = []

    def fake_command_runner(cmd: List[str], input: str = "", **kwargs: Any) -> subprocess.CompletedProcess:
        captured_commands.append(cmd)
        captured_inputs.append(input)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="4\n",
            stderr="",
        )

    runner = DockerRunner(command_runner=fake_command_runner)
    req = ExecutionRequest(
        language="python",
        code="print(2 + 2)",
    )

    result = runner.execute(req)

    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert result.stdout == "4\n"
    assert result.stderr == ""

    assert len(captured_commands) == 1
    cmd = captured_commands[0]

    # Verify Docker binary and run flags
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "-i" in cmd

    # Verify strict security isolation options
    assert "--network" in cmd
    net_idx = cmd.index("--network")
    assert cmd[net_idx + 1] == "none"

    assert "--memory=512m" in cmd or ("--memory" in cmd and cmd[cmd.index("--memory") + 1] == "512m")
    assert "--cpus=1.0" in cmd or ("--cpus" in cmd and cmd[cmd.index("--cpus") + 1] == "1.0")
    assert "--read-only" in cmd

    # Verify tmpfs mount
    assert "--tmpfs" in cmd
    tmpfs_idx = cmd.index("--tmpfs")
    assert "/tmp" in cmd[tmpfs_idx + 1]

    # Verify image & execution
    assert "python:3.12-slim" in cmd
    assert "python" in cmd
    assert "-B" in cmd
    assert "-" in cmd

    # Verify code provided to stdin
    assert captured_inputs[0] == "print(2 + 2)"


def test_docker_runner_cli_structure_shell_and_python_distinction():
    """Verify that DockerRunner builds correct CLI for shell vs python requests without needing Docker."""
    runner = DockerRunner()

    py_req = ExecutionRequest(language="python", code="print(2 + 2)")
    py_cmd = runner.build_command(py_req, container_name="test-py")
    assert py_cmd[-3:] == ["python", "-B", "-"]

    sh_req = ExecutionRequest(language="shell", code="echo 'test-shell'")
    sh_cmd = runner.build_command(sh_req, container_name="test-sh")
    assert sh_cmd[-3:] == ["sh", "-c", "echo 'test-shell'"]

    # Also test fake execution verifies stdin behavior
    captured: dict = {}

    def fake_runner(cmd: List[str], input: Any = None, **kwargs: Any) -> subprocess.CompletedProcess:
        captured["cmd"] = cmd
        captured["input"] = input
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="out", stderr="")

    mock_runner = DockerRunner(command_runner=fake_runner)

    mock_runner.execute(py_req)
    assert captured["cmd"][-3:] == ["python", "-B", "-"]
    assert captured["input"] == "print(2 + 2)"

    mock_runner.execute(sh_req)
    assert captured["cmd"][-3:] == ["sh", "-c", "echo 'test-shell'"]
    assert captured["input"] is None


def test_docker_runner_handles_timeout_with_fake_runner():
    """Verify that TimeoutExpired returns SandboxStatus.TIMEOUT and exit_code -1."""
    def fake_command_runner(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30.0)

    runner = DockerRunner(command_runner=fake_command_runner)
    req = ExecutionRequest(
        language="python",
        code="while True: pass",
        limits=ResourceLimits(timeout_seconds=30.0),
    )

    result = runner.execute(req)

    assert result.status == SandboxStatus.TIMEOUT
    assert result.exit_code == -1
    assert "timed out after 30.0 seconds" in result.stderr.lower()


def test_docker_runner_handles_nonzero_exit_and_stderr():
    """Verify that failed script execution captures exit code and stderr."""
    def fake_command_runner(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr="ZeroDivisionError: division by zero\n",
        )

    runner = DockerRunner(command_runner=fake_command_runner)
    req = ExecutionRequest(
        language="python",
        code="1 / 0",
    )

    result = runner.execute(req)

    assert result.status == SandboxStatus.FAILED
    assert result.exit_code == 1
    assert "ZeroDivisionError" in result.stderr


@pytest.mark.disallow_local
def test_local_process_runner_blocked_when_env_not_set(tmp_path):
    """LocalProcessRunner must block execution when SANDBOX_ALLOW_LOCAL is not 1."""
    runner = LocalProcessRunner(SecurityGovernor())
    req = ExecutionRequest(
        language="python",
        code="print('should not run')",
    )
    result = runner.execute(req, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.BLOCKED
    assert result.exit_code == -1
    assert "SANDBOX_ALLOW_LOCAL=1" in result.stderr


def test_local_process_runner_allowed_when_env_set(tmp_path, monkeypatch):
    """LocalProcessRunner allows execution when SANDBOX_ALLOW_LOCAL=1 is set."""
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    runner = LocalProcessRunner(SecurityGovernor())
    req = ExecutionRequest(
        language="python",
        code="print('local allowed')",
    )
    result = runner.execute(req, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert "local allowed" in result.stdout


def test_sandbox_manager_defaults_to_docker_runner(monkeypatch):
    """SandboxManager initializes with DockerRunner when Docker is available."""
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: True)
    mgr = SandboxManager()
    assert isinstance(mgr.runner, DockerRunner)


# ==============================================================================
# Live Tests (Skipped unless Docker is available)
# ==============================================================================

@pytest.fixture
def live_docker_runner():
    runner = DockerRunner()
    if not runner.is_docker_available():
        pytest.skip("Docker daemon is not available on this machine")
    return runner


@pytest.mark.live
def test_docker_live_print_math(live_docker_runner):
    """Live Test 1: print(2+2) returns 4."""
    result = live_docker_runner.run_python("print(2 + 2)")
    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert result.stdout.strip() == "4"


@pytest.mark.live
def test_docker_live_infinite_loop_timeout(live_docker_runner):
    """Live Test 2: while True: pass is killed at the timeout."""
    req = ExecutionRequest(
        language="python",
        code="while True:\n    pass",
        limits=ResourceLimits(timeout_seconds=2.0),
    )
    result = live_docker_runner.execute(req)
    assert result.status == SandboxStatus.TIMEOUT
    assert result.exit_code == -1
    assert "timed out" in result.stderr.lower()


@pytest.mark.live
def test_docker_live_network_call_fails(live_docker_runner):
    """Live Test 3: a network call fails under --network none."""
    code = """
import urllib.request
urllib.request.urlopen("https://example.com", timeout=2)
"""
    result = live_docker_runner.run_python(code)
    assert result.status in (SandboxStatus.FAILED, SandboxStatus.BLOCKED)
    assert result.exit_code != 0
    assert result.stderr
    if result.status == SandboxStatus.BLOCKED:
        assert "network access is disabled" in result.stderr.lower()


@pytest.mark.live
def test_docker_live_writing_outside_tmp_fails(live_docker_runner):
    """Live Test 4: writing outside /tmp fails on read-only root filesystem."""
    code = """
# Writing inside /tmp must succeed (tmpfs)
with open('/tmp/ok_file.txt', 'w') as f:
    f.write('TMP_OK')

# Writing outside /tmp must raise OSError (Read-only file system)
with open('/outside_disallowed.txt', 'w') as f:
    f.write('FAIL')
"""
    result = live_docker_runner.run_python(code)
    assert result.status == SandboxStatus.FAILED
    assert result.exit_code != 0
    assert "read-only file system" in result.stderr.lower() or "errno 30" in result.stderr.lower()


@pytest.mark.live
def test_docker_live_shell_command(live_docker_runner):
    """Live Test 5: a shell command executes via sh inside container."""
    req = ExecutionRequest(
        language="shell",
        code="echo 'live-shell-active'",
    )
    result = live_docker_runner.execute(req)
    assert result.status == SandboxStatus.SUCCESS
    assert result.exit_code == 0
    assert "live-shell-active" in result.stdout
