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
from sandboxes.runner.local_process_runner import LocalProcessRunner


def test_sandbox_valid_code_returns_stdout():
    manager = SandboxManager()
    res = manager.execute("print('Hello from sandboxed environment!')")
    assert res.status == SandboxStatus.SUCCESS
    assert "Hello from sandboxed environment!" in res.stdout
    assert res.exit_code == 0


def test_sandbox_infinite_loop_raises_timeout_error():
    manager = SandboxManager()
    # Code that attempts infinite loop, with 0.2s timeout
    with pytest.raises(SandboxTimeoutError) as exc_info:
        manager.execute("while True: pass", timeout_seconds=0.2, raise_on_timeout=True)

    assert "timed out" in str(exc_info.value).lower()


def test_docker_engine_fallback_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    engine = DockerExecutionEngine(fallback_runner=LocalProcessRunner(SecurityGovernor()))
    engine._docker_available = False

    req = ExecutionRequest(
        code="print(10 + 20)",
        limits=ResourceLimits(timeout_seconds=5.0),
    )
    result = engine.execute(req, scratch_dir=str(tmp_path / "docker_test"))
    assert result.status == SandboxStatus.SUCCESS
    assert "30" in result.stdout


def test_e2b_engine_fallback_when_no_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    engine = E2BExecutionEngine(
        api_key=None,
        fallback_runner=LocalProcessRunner(SecurityGovernor()),
    )
    req = ExecutionRequest(
        code="print('Fallback execution')",
        limits=ResourceLimits(timeout_seconds=5.0),
    )
    result = engine.execute(req, scratch_dir=str(tmp_path / "e2b_test"))
    assert result.status == SandboxStatus.SUCCESS
    assert "Fallback execution" in result.stdout
