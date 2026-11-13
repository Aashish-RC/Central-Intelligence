"""Test suite for Sandbox execution, isolation, and security policy checks."""

import pytest
from agent.core.manifest import SandboxConfig
from agent.core.exceptions import SandboxExecutionError
from agent.sandbox.local_docker_adapter import LocalDockerSandboxAdapter
from agent.sandbox.e2b_adapter import E2BSandboxAdapter


@pytest.mark.asyncio
async def test_local_sandbox_safe_command(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    sandbox = LocalDockerSandboxAdapter(allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=10)

    res = await sandbox.execute_command(
        command="echo 'phoenix-sandbox-active'",
        config=config,
        trusted_local_path=True,
    )
    assert res["exit_code"] == 0
    assert "phoenix-sandbox-active" in res["stdout"]
    assert res["execution_time_ms"] > 0


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
    sandbox = LocalDockerSandboxAdapter(allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=10)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await sandbox.execute_command(
            command="echo 'in-production'",
            config=config,
            trusted_local_path=True,
        )

    assert "Host subprocess execution is strictly forbidden in production" in str(exc_info.value)


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
