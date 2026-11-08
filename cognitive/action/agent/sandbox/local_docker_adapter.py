"""Fallback Local Docker / Subprocess Execution Sandbox."""

import asyncio
import os
import shlex
import time
from typing import Any, Dict, List, Optional
from agent.core.manifest import SandboxConfig
from agent.core.exceptions import SandboxExecutionError


class LocalDockerSandboxAdapter:
    """Local execution sandbox with timeout enforcement delegating to canonical SandboxManager."""

    DANGEROUS_COMMANDS: List[str] = [
        "rm -rf /",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "chmod -R 777 /",
    ]

    def __init__(self, manager: Optional[Any] = None):
        self.manager = manager
        if self.manager is None:
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
                    os.environ.setdefault("SANDBOX_ALLOW_LOCAL", "1")
                    runner = DeviceRunner(gov)
                self.manager = SandboxManager(governor=gov, device_runner=runner)
            except ImportError:
                self.manager = None

    async def run_command(
        self,
        command: str,
        project_id: str = "default",
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        """Run command through canonical SandboxManager."""
        if self.manager and hasattr(self.manager, "run_command"):
            return await self.manager.run_command(command, project_id=project_id, timeout_seconds=timeout_seconds)
        config = SandboxConfig(timeout_seconds=int(timeout_seconds or 60))
        return await self.execute_command(command, config=config)

    async def execute_command(
        self,
        command: str,
        config: Optional[SandboxConfig] = None,
        cwd: Optional[str] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Execute a command locally in a guarded subprocess with timeout."""
        # Check dangerous patterns
        for bad in self.DANGEROUS_COMMANDS:
            if bad in command:
                raise SandboxExecutionError(
                    f"Command blocked by local sandbox security policy: '{bad}'",
                    details={"blocked_command": bad}
                )

        if self.manager and hasattr(self.manager, "execute_command"):
            try:
                return await self.manager.execute_command(command, config=config, cwd=cwd, project_id=project_id)
            except SandboxExecutionError:
                raise
            except Exception:
                pass  # Fall through to guarded subprocess

        start_time = time.perf_counter()
        timeout = config.timeout_seconds if config else 60

        try:
            # Use asyncio create_subprocess_shell
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
                "provider": "local-subprocess",
            }

        except SandboxExecutionError:
            raise
        except Exception as e:
            raise SandboxExecutionError(f"Subprocess execution error: {str(e)}")

