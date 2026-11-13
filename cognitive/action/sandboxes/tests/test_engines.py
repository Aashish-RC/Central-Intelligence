"""Unit tests for E2B and Docker execution engines and timeout error raising."""

import pytest
from unittest.mock import MagicMock, patch

from sandboxes.core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxStatus,
    SandboxTimeoutError,
)
from sandboxes.core.engines import E2BExecutionEngine, DockerExecutionEngine
from sandboxes.governor.security_governor import SecurityGovernor
from sandboxes.manager import SandboxManager
from sandboxes.runner.device_runner import DeviceRunner
from sandboxes.runner.docker_runner import DockerRunner
from sandboxes.runner.local_process_runner import LocalProcessRunner


def test_sandbox_valid_code_returns_stdout(test_trusted_context):
    runner = DeviceRunner(trusted_context=test_trusted_context)
    manager = SandboxManager(device_runner=runner)
    res = manager.execute("print('Hello from sandboxed environment!')")
    assert res.status == SandboxStatus.SUCCESS
    assert "Hello from sandboxed environment!" in res.stdout
    assert res.exit_code == 0


def test_sandbox_infinite_loop_raises_timeout_error(test_trusted_context):
    runner = DeviceRunner(trusted_context=test_trusted_context)
    manager = SandboxManager(device_runner=runner)
    # Code that attempts infinite loop, with 0.2s timeout
    with pytest.raises(SandboxTimeoutError) as exc_info:
        manager.execute("while True: pass", timeout_seconds=0.2, raise_on_timeout=True)

    assert "timed out" in str(exc_info.value).lower()


def test_sandbox_manager_fails_closed_when_docker_unavailable(monkeypatch):
    """Untrusted invocation of SandboxManager fails closed when Docker is unavailable."""
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: False)
    manager = SandboxManager()
    res = manager.execute("print('untrusted')")
    assert res.status == SandboxStatus.BLOCKED
    assert "unavailable" in res.stderr.lower()


def test_sandbox_manager_blocks_host_in_production(test_trusted_context, monkeypatch):
    """SandboxManager blocks host execution in production even if trusted context is passed."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    runner = DeviceRunner(trusted_context=test_trusted_context)
    manager = SandboxManager(device_runner=runner)
    res = manager.execute("print('should be blocked')")
    assert res.status == SandboxStatus.BLOCKED
    assert "strictly forbidden in production" in res.stderr.lower()


def test_docker_engine_fails_closed_when_unavailable(tmp_path):
    engine = DockerExecutionEngine()
    engine._docker_available = False

    req = ExecutionRequest(
        code="print(10 + 20)",
        limits=ResourceLimits(timeout_seconds=5.0),
    )
    result = engine.execute(req, scratch_dir=str(tmp_path / "docker_test"))
    assert result.status == SandboxStatus.BLOCKED
    assert "unavailable" in result.stderr.lower()


def test_e2b_engine_fails_closed_when_no_api_key_and_docker_unavailable(tmp_path):
    engine = E2BExecutionEngine(
        api_key=None,
    )
    if hasattr(engine._fallback_runner, "_docker_available"):
        engine._fallback_runner._docker_available = False
    req = ExecutionRequest(
        code="print('Fallback execution')",
        limits=ResourceLimits(timeout_seconds=5.0),
    )
    result = engine.execute(req, scratch_dir=str(tmp_path / "e2b_test"))
    assert result.status == SandboxStatus.BLOCKED
