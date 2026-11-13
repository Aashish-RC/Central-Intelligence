"""Test suite for Sandbox execution, isolation, and security policy checks."""

import pytest
from agent.core.manifest import SandboxConfig
from agent.core.exceptions import SandboxExecutionError
from agent.sandbox.local_docker_adapter import LocalDockerSandboxAdapter
from agent.sandbox.e2b_adapter import E2BSandboxAdapter


@pytest.mark.asyncio
async def test_local_sandbox_safe_command(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import AsyncMock
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    mock_mgr = AsyncMock()
    mock_mgr.execute_command.return_value = {
        "exit_code": 0,
        "stdout": "phoenix-sandbox-active\n",
        "stderr": "",
        "execution_time_ms": 12.5,
        "status": "success",
    }
    sandbox = LocalDockerSandboxAdapter(manager=mock_mgr, allow_local_fallback=False)
    config = SandboxConfig(required=True, timeout_seconds=10)

    res = await sandbox.execute_command(
        command="echo 'phoenix-sandbox-active'",
        config=config,
    )
    assert res["exit_code"] == 0
    assert "phoenix-sandbox-active" in res["stdout"]
    assert res["execution_time_ms"] > 0
    mock_mgr.execute_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_sandbox_prohibits_unauthorized_host_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SANDBOX_ALLOW_LOCAL", raising=False)
    sandbox = LocalDockerSandboxAdapter(manager=None, allow_local_fallback=False)
    config = SandboxConfig(required=True, timeout_seconds=10)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox.execute_command(command="echo 'unauthorized'", config=config)

    assert "Prohibited sandbox fallback" in str(exc_info.value)


@pytest.mark.asyncio
async def test_local_sandbox_prohibits_host_execution_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    config = SandboxConfig(required=True, timeout_seconds=10)

    # Case 1: When container manager is unavailable in production, host execution is unconditionally blocked
    sandbox_no_mgr = LocalDockerSandboxAdapter(manager=None, allow_local_fallback=True)
    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox_no_mgr.execute_command(
            command="echo 'in-production'",
            config=config,
            trusted_local_path=True,
        )
    assert "Host subprocess execution is strictly forbidden in production" in str(exc_info.value)

    # Case 2: When container execution encounters an error in production, fallback to host is prohibited
    from unittest.mock import AsyncMock, MagicMock
    mock_mgr = MagicMock()
    mock_mgr.execute_command = AsyncMock(side_effect=RuntimeError("Docker daemon connection failed"))
    sandbox_docker_err = LocalDockerSandboxAdapter(manager=mock_mgr, allow_local_fallback=True)
    with pytest.raises(SandboxExecutionError) as exc_info2:
        await sandbox_docker_err.execute_command(
            command="echo 'in-production'",
            config=config,
            trusted_local_path=True,
        )
    assert "Prohibited sandbox fallback" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_local_sandbox_blocks_command_injection(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    sandbox = LocalDockerSandboxAdapter(allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=10)

    # Command chaining trying to read /etc/passwd
    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox.execute_command(command="echo hi; cat /etc/passwd", config=config)
    assert "security policy" in str(exc_info.value)

    # Attempting to read private ssh keys
    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox.execute_command(command="cat .ssh/id_rsa", config=config)
    assert "security policy" in str(exc_info.value)


@pytest.mark.asyncio
async def test_local_sandbox_blocks_dangerous_command():
    sandbox = LocalDockerSandboxAdapter()
    config = SandboxConfig(required=True, timeout_seconds=10)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox.execute_command(command="rm -rf / --no-preserve-root", config=config)

    assert "security policy" in str(exc_info.value)


@pytest.mark.asyncio
async def test_e2b_adapter_fallback():
    # E2B adapter running without cloud key falls back cleanly
    adapter = E2BSandboxAdapter(api_key=None)
    config = SandboxConfig(required=True, template="python-3.11-data-science")

    res = await adapter.execute_command(command="python -c 'print(1+1)'", config=config)
    assert res["exit_code"] == 0
    assert "Simulated" in res["stdout"] or "e2b" in res["provider"]
