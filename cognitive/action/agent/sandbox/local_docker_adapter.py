"""Guarded Local Execution Sandbox with Strict Fallback Prevention."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import time
from typing import Any, Dict, List, Optional, Pattern

from agent.core.exceptions import SandboxExecutionError
from agent.core.manifest import SandboxConfig
from control.safety.production_guard import is_production

BLOCKED_COMMAND_PATTERNS: List[Pattern] = [
    re.compile(r"rm\s+-rf\s+(?:/|--no-preserve-root)", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=/dev/zero\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+(?:-R\s+)?777\s+/", re.IGNORECASE),
    re.compile(r"(?:/etc/shadow|/etc/passwd|SAM|SYSTEM32[\/\\]config)", re.IGNORECASE),
    re.compile(r"(?:^|[\/\\\'\"\s])(?:\.vault_key|\.ssh[\/\\]id_rsa|\.ssh[\/\\]id_ed25519)(?:$|[\/\\\'\"\s])", re.IGNORECASE),
    re.compile(r"\b(?:nc|netcat)\b.*?-e\s+", re.IGNORECASE),
    re.compile(r"/dev/tcp/\d+/\d+", re.IGNORECASE),
]


_DEFAULT_MANAGER = object()


class LocalDockerSandboxAdapter:
    """Local execution sandbox with timeout enforcement delegating to canonical SandboxManager.

    Strictly eliminates silent fallback from isolated containers to host shell execution.
    """

    DANGEROUS_COMMANDS: List[str] = [
        "rm -rf /",
        "rm -rf --no-preserve-root",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "chmod -R 777 /",
        "/etc/passwd",
        "/etc/shadow",
        ".ssh/id_rsa",
    ]

    def __init__(
        self,
        manager: Any = _DEFAULT_MANAGER,
        allow_local_fallback: bool = False,
    ):
        self.allow_local_fallback = allow_local_fallback
        if manager is _DEFAULT_MANAGER:
            try:
                from sandboxes.manager import SandboxManager
                from sandboxes.runner.device_runner import DeviceRunner
                from sandboxes.runner.docker_runner import DockerRunner
                from sandboxes.governor.security_governor import SecurityGovernor

                gov = SecurityGovernor()
                dk = DockerRunner(gov)
                if dk.is_docker_available():
                    runner = dk
                else:
                    # Do NOT silently default SANDBOX_ALLOW_LOCAL=1
                    runner = DeviceRunner(gov)
                self.manager = SandboxManager(governor=gov, device_runner=runner)
            except ImportError:
                self.manager = None
        else:
            self.manager = manager

    def validate_command_security(self, command: str) -> None:
        """Inspect command for security violations and injection attempts."""
        for bad in self.DANGEROUS_COMMANDS:
            if bad in command:
                raise SandboxExecutionError(
                    f"Command blocked by local sandbox security policy: '{bad}'",
                    details={"blocked_command": bad},
                )

        for pat in BLOCKED_COMMAND_PATTERNS:
            if pat.search(command):
                raise SandboxExecutionError(
                    f"Command blocked by security policy: matched prohibited pattern '{pat.pattern}'",
                    details={"matched_pattern": pat.pattern},
                )

    async def run_command(
        self,
        command: str,
        project_id: str = "default",
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        """Run command through canonical SandboxManager."""
        config = SandboxConfig(timeout_seconds=int(timeout_seconds or 60))
        return await self.execute_command(command, config=config, project_id=project_id)

    async def execute_command(
        self,
        command: str,
        config: Optional[SandboxConfig] = None,
        cwd: Optional[str] = None,
        project_id: str = "default",
        trusted_local_path: bool = False,
    ) -> Dict[str, Any]:
        """Execute command in sandbox, strictly prohibiting unauthorized host shell fallback."""
        self.validate_command_security(command)

        # 1. Try execution via SandboxManager
        if self.manager and hasattr(self.manager, "execute_command"):
            try:
                res = await self.manager.execute_command(
                    command, config=config, cwd=cwd, project_id=project_id
                )
                if isinstance(res, dict) and res.get("status") == "blocked":
                    raise SandboxExecutionError(
                        f"Execution blocked by sandbox governor: {res.get('stderr')}"
                    )
                return res
            except SandboxExecutionError:
                raise
            except Exception as mgr_err:
                # If manager raised because docker is unavailable, do NOT silently fall through to host shell
                has_local_auth = (
                    self.allow_local_fallback
                    or trusted_local_path
                    or os.getenv("SANDBOX_ALLOW_LOCAL") == "1"
                )
                if not has_local_auth or is_production():
                    raise SandboxExecutionError(
                        f"Prohibited sandbox fallback: Container execution failed and host fallback is prohibited: {mgr_err}"
                    ) from mgr_err

        # 2. Check if local host execution is permitted
        # Host execution is unconditionally forbidden in production
        if is_production():
            raise SandboxExecutionError(
                "Prohibited sandbox fallback: Host subprocess execution is strictly forbidden in production. "
                "Hardened container execution (Docker or E2B) is mandatory."
            )

        # In dev/test, explicit authorization via SANDBOX_ALLOW_LOCAL=1 or trusted parameter is required
        has_local_auth = (
            self.allow_local_fallback
            or trusted_local_path
            or os.getenv("SANDBOX_ALLOW_LOCAL") == "1"
        )
        if not has_local_auth:
            raise SandboxExecutionError(
                "Prohibited sandbox fallback: Docker container is unavailable and local host execution "
                "is disabled. Set SANDBOX_ALLOW_LOCAL=1 or authorize via trusted_local_path=True."
            )

        # 3. Authorized trusted local execution path
        start_time = time.perf_counter()
        timeout = config.timeout_seconds if config else 60

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout),
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise SandboxExecutionError(f"Command timed out after {timeout} seconds: '{command}'")

            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "exit_code": proc.returncode,
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "execution_time_ms": duration_ms,
                "provider": "authorized-local-subprocess",
            }

        except SandboxExecutionError:
            raise
        except Exception as e:
            raise SandboxExecutionError(f"Subprocess execution error: {str(e)}")

