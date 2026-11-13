"""Deterministic Adversarial Regression Suite for Execution Isolation and Configuration Hardening.

Covers Mission 06 Acceptance Criteria:
1. Encoded commands (base64, hex, quote concatenation, obfuscation)
2. Shell metacharacters (&&, ||, ;, |, backticks, command substitution $())
3. Nested subshells (bash -c, sh -c, eval)
4. Sandbox failure and unauthorized fallback (fail-closed behavior)
5. Context spoofing and authorization boundary enforcement
6. Production aliases and conflicting environment settings
"""

import base64
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from control.safety.production_guard import (
    is_production,
    get_environment_name,
    ProductionSafetyError,
)
from agent.config import AgentLayerConfig
from agent.core.exceptions import SandboxExecutionError
from agent.core.manifest import SandboxConfig
from agent.sandbox.local_docker_adapter import LocalDockerSandboxAdapter
from sandboxes.core.models import ExecutionRequest, ResourceLimits, SandboxStatus
from sandboxes.manager import SandboxManager
from sandboxes.runner.device_runner import DeviceRunner
from sandboxes.runner.docker_runner import DockerRunner
from sandboxes.runner.local_process_runner import LocalProcessRunner
from sandboxes.trusted_host import (
    TrustedExecutionContext,
    TrustedHostExecutionError,
    TrustedHostExecutionPolicy,
    TrustedHostProcessRunner,
    TRUSTED_HOST_TOKEN_ENV,
)


# ==============================================================================
# 1. Adversarial Encoded & Obfuscated Commands
# ==============================================================================

ADVERSARIAL_PAYLOADS = [
    # Base64 encoded payload: "cat /etc/passwd"
    f"echo {base64.b64encode(b'cat /etc/passwd').decode()} | base64 -d | sh",
    # Quote obfuscation bypassing simple regex
    "c'a't /etc/p''asswd",
    'c"a"t /etc/p""asswd',
    # Hex decoding evasion
    "python3 -c \"import binascii; print(binascii.unhexlify('636174202f6574632f706173737764'))\"",
    # Environment variable expansion injection
    "CMD=passwd; cat /etc/$CMD",
    # Path traversal with wildcard
    "/bin/c*t /etc/pass*",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ADVERSARIAL_PAYLOADS)
async def test_adversarial_payloads_never_reach_host_without_container(payload, monkeypatch):
    """Adversarial obfuscated commands MUST fail closed if container execution is unavailable.

    They must never fall back to host execution regardless of environment flags.
    """
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)

    adapter = LocalDockerSandboxAdapter(manager=None, allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=5)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command(command=payload, config=config, trusted_local_path=True)

    err_msg = str(exc_info.value).lower()
    assert "security policy" in err_msg or "prohibited sandbox fallback" in err_msg or "untrusted host execution" in err_msg


# ==============================================================================
# 2. Shell Metacharacters & Nested Subshells
# ==============================================================================

SHELL_INJECTION_VECTORS = [
    "echo safe && id",
    "echo safe || id",
    "echo safe ; id",
    "echo safe | id",
    "echo `id`",
    "echo $(id)",
    "bash -c 'id'",
    "sh -c 'id'",
    "eval 'id'",
    "exec 5<>/dev/tcp/127.0.0.1/80",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("vector", SHELL_INJECTION_VECTORS)
async def test_shell_metacharacters_cannot_execute_on_host(vector, monkeypatch):
    """Shell injection vectors must be blocked or fail closed to prevent host execution."""
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    adapter = LocalDockerSandboxAdapter(manager=None, allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=5)

    with pytest.raises(SandboxExecutionError):
        await adapter.execute_command(command=vector, config=config, trusted_local_path=True)


# ==============================================================================
# 3. Sandbox Failure & Unauthorized Fallback
# ==============================================================================

@pytest.mark.asyncio
async def test_container_manager_failure_fails_closed_without_host_fallback():
    """When container manager raises an error, it must fail closed and NOT execute on host."""
    mock_mgr = MagicMock()
    mock_mgr.execute_command = AsyncMock(side_effect=RuntimeError("Docker socket connection reset"))

    adapter = LocalDockerSandboxAdapter(manager=mock_mgr, allow_local_fallback=True)
    config = SandboxConfig(required=True, timeout_seconds=5)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command(
            command="echo 'do-not-fallback'",
            config=config,
            trusted_local_path=True,
        )

    assert "Prohibited sandbox fallback" in str(exc_info.value)
    assert "host fallback is prohibited" in str(exc_info.value)


def test_docker_runner_fails_closed_when_docker_daemon_stops(monkeypatch):
    """DockerRunner.execute() must return SandboxStatus.BLOCKED when Docker is unavailable."""
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: False)
    runner = DockerRunner()
    req = ExecutionRequest(language="python", code="print('isolated')")
    result = runner.execute(req)

    assert result.status == SandboxStatus.BLOCKED
    assert result.exit_code == -1
    assert "Hardened container execution (Docker) is unavailable" in result.stderr


def test_local_process_runner_rejects_untrusted_requests_even_with_sandbox_allow_local(monkeypatch, tmp_path):
    """SANDBOX_ALLOW_LOCAL=1 alone does NOT authorize LocalProcessRunner."""
    monkeypatch.setenv("SANDBOX_ALLOW_LOCAL", "1")
    runner = LocalProcessRunner()
    req = ExecutionRequest(language="python", code="print('escape attempt')")
    result = runner.execute(req, scratch_dir=str(tmp_path))

    assert result.status == SandboxStatus.BLOCKED
    assert "Untrusted command execution on the host machine is strictly prohibited" in result.stderr


# ==============================================================================
# 4. Context Spoofing & Authorization Boundary Enforcement
# ==============================================================================

@pytest.mark.parametrize("caller", [
    "agent", "Agent", "AGENT_RUNNER", "untrusted_agent", "llm-executor", "external_tool", "prompt_injection"
])
def test_untrusted_caller_spoofing_rejected(caller, monkeypatch):
    """TrustedHostExecutionPolicy must reject any caller ID resembling agent or untrusted entities."""
    monkeypatch.setenv(TRUSTED_HOST_TOKEN_ENV, "valid-secret-token")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")

    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id=caller,
        capability="TEST_FIXTURE_EXECUTION",
        auth_token="valid-secret-token",
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)

    assert "Unauthorized caller" in str(exc_info.value)


def test_forged_token_rejected(monkeypatch):
    """Context with forged auth token must fail closed."""
    monkeypatch.setenv(TRUSTED_HOST_TOKEN_ENV, "super-secret-system-token")
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "development")

    policy = TrustedHostExecutionPolicy()
    ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="TEST_FIXTURE_EXECUTION",
        auth_token="wrong-guessed-token",
    )
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        policy.validate_context(ctx)

    assert "Invalid auth_token" in str(exc_info.value)


# ==============================================================================
# 5. Production Aliases & Conflicting Environment Settings
# ==============================================================================

@pytest.mark.parametrize("alias", ["prod", "production", "live", "PROD", "PRODUCTION", "LIVE"])
def test_production_aliases_consistently_identified_as_production(alias, monkeypatch):
    """All production aliases must be recognized as production."""
    monkeypatch.setenv("ENVIRONMENT", alias)
    monkeypatch.delenv("ENV", raising=False)
    assert is_production() is True


def test_conflicting_env_and_environment_rejected_by_validator(monkeypatch):
    """Conflicting ENV and ENVIRONMENT settings must be rejected."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(ProductionSafetyError) as exc_info:
        get_environment_name()

    assert "Conflicting environment configuration" in str(exc_info.value)


def test_conflicting_env_rejected_by_agent_layer_config(monkeypatch):
    """AgentLayerConfig must refuse to initialize when ENV and ENVIRONMENT conflict."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "development")

    with pytest.raises((ValueError, ProductionSafetyError)) as exc_info:
        AgentLayerConfig()

    assert "Conflicting environment configuration" in str(exc_info.value)


def test_agent_layer_config_aligns_with_canonical_production_guard(monkeypatch):
    """AgentLayerConfig.environment must correctly reflect production from ENV alias."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    config = AgentLayerConfig()
    assert config.environment == "production"
    assert is_production() is True


@pytest.mark.parametrize("prod_val", ["production", "prod", "live"])
def test_all_runners_unconditionally_block_host_in_production(prod_val, monkeypatch, tmp_path):
    """Every runner must unconditionally block host execution when in production."""
    monkeypatch.setenv("ENVIRONMENT", prod_val)
    monkeypatch.setenv("ENV", prod_val)
    monkeypatch.setenv(TRUSTED_HOST_TOKEN_ENV, "valid-token")

    trusted_ctx = TrustedExecutionContext(
        caller_id="orchestrator",
        capability="TEST_FIXTURE_EXECUTION",
        auth_token="valid-token",
    )

    # 1. LocalProcessRunner
    local_runner = LocalProcessRunner()
    req = ExecutionRequest(
        language="python",
        code="print('prod-test')",
        trusted_context=trusted_ctx,
    )
    res1 = local_runner.execute(req, scratch_dir=str(tmp_path / "1"))
    assert res1.status == SandboxStatus.BLOCKED
    assert "strictly forbidden in production" in res1.stderr

    # 2. DeviceRunner
    device_runner = DeviceRunner(trusted_context=trusted_ctx)
    res2 = device_runner.run_shell("echo prod-test", scratch_dir=str(tmp_path / "2"))
    assert res2.status == SandboxStatus.BLOCKED
    assert "strictly forbidden in production" in res2.stderr

    # 3. TrustedHostProcessRunner
    trusted_runner = TrustedHostProcessRunner()
    with pytest.raises(TrustedHostExecutionError) as exc_info:
        trusted_runner.execute_trusted_command(
            command_argv=["python3", "-c", "print('prod-test')"],
            context=trusted_ctx,
        )
    assert "strictly forbidden in production" in str(exc_info.value)
