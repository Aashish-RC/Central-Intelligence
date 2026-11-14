"""Live integration tests for E2B / Local Docker Sandbox Adapter (Layer 5).

Executed against a live Docker daemon or E2B Cloud microVM.
Skipped in hermetic/CI test mode unless SANDBOX_LIVE=1 is explicitly set.
"""

from __future__ import annotations

import os
import pytest

from agent.core.exceptions import SandboxExecutionError
from agent.core.manifest import SandboxConfig
from agent.sandbox.e2b_adapter import E2BSandboxAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

SANDBOX_LIVE = os.getenv("SANDBOX_LIVE")


@pytest.mark.asyncio
async def test_python_code_executes_and_returns_real_stdout():
    """Execute real Python in container/microVM and verify actual computed stdout."""
    if SANDBOX_LIVE != "1":
        pytest.skip("SANDBOX_LIVE=1 not set; skipping live sandbox tests")

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=15)

    result = await adapter.execute_command(
        command="python3 -c 'print(2+2)'",
        config=config,
    )

    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "4"


@pytest.mark.asyncio
async def test_command_failure_returns_nonzero_exit_code():
    """Execute Python code that exits with code 7 and verify non-zero exit propagation."""
    if SANDBOX_LIVE != "1":
        pytest.skip("SANDBOX_LIVE=1 not set; skipping live sandbox tests")

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=15)

    result = await adapter.execute_command(
        command="python3 -c 'import sys; sys.exit(7)'",
        config=config,
    )

    assert result["exit_code"] == 7


@pytest.mark.asyncio
async def test_command_timeout_is_enforced():
    """Verify execution exceeding timeout is aborted with SandboxExecutionError or non-zero exit."""
    if SANDBOX_LIVE != "1":
        pytest.skip("SANDBOX_LIVE=1 not set; skipping live sandbox tests")

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=2)

    with pytest.raises(SandboxExecutionError):
        await adapter.execute_command("sleep 30", config=config)


@pytest.mark.asyncio
async def test_dangerous_command_blocked():
    """Verify dangerous destructive commands are blocked by sandbox security policies."""
    if SANDBOX_LIVE != "1":
        pytest.skip("SANDBOX_LIVE=1 not set; skipping live sandbox tests")

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=10)

    with pytest.raises(SandboxExecutionError):
        await adapter.execute_command("rm -rf /", config=config)


@pytest.mark.asyncio
async def test_no_docker_no_e2b_fails_closed(monkeypatch):
    """When ADAPTER_MODE=live, no Docker daemon, no E2B key, fail closed with ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    from sandboxes.runner.docker_runner import DockerRunner
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: False)

    adapter = E2BSandboxAdapter(api_key=None, _defer_prod_check=True)
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        await adapter.execute_command("echo hi")

