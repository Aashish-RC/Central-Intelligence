"""Sandbox Manager: Ephemeral scratchpad lifecycle orchestration and cleanups."""

from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, Optional
from .core.interfaces import BaseDeviceRunner, BaseSandboxManager
from .core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
    SandboxTimeoutError,
)
import os
from .core.engines import E2BExecutionEngine, DockerExecutionEngine
from .governor.security_governor import SecurityGovernor
from .runner.device_runner import DeviceRunner
from .runner.docker_runner import DockerRunner


class SandboxManager(BaseSandboxManager):
    """Orchestrates isolated ephemeral execution lifecycles with deterministic destruction."""

    def __init__(
        self,
        governor: Optional[SecurityGovernor] = None,
        device_runner: Optional[BaseDeviceRunner] = None,
        engine: Optional[BaseDeviceRunner] = None,
        permission_service: Optional[Any] = None,
        enforce_permissions: bool = False,
    ):
        self.governor = governor or SecurityGovernor()
        self.permission_service = permission_service
        self.enforce_permissions = enforce_permissions or os.getenv("PHEONIX_SANDBOX_PERMISSIONS") == "1"

        if engine or device_runner:
            self.runner = engine or device_runner
        else:
            docker_runner = DockerRunner(self.governor)
            if docker_runner.is_docker_available():
                self.runner = docker_runner
            elif os.getenv("SANDBOX_ALLOW_LOCAL") == "1":
                self.runner = DeviceRunner(self.governor)
            else:
                self.runner = docker_runner

    def run(
        self,
        request: ExecutionRequest,
        raise_on_timeout: bool = False,
        permission_service: Optional[Any] = None,
    ) -> SandboxResult:
        perm_svc = permission_service or self.permission_service
        if self.enforce_permissions or perm_svc is not None:
            try:
                from permissions import check_permission, ApprovalStatus, ActionType

                # Intercept file writing
                if request.files:
                    decision = check_permission(
                        ActionType.FS_WRITE,
                        resource=",".join(request.files.keys()),
                        project_id=request.project_id,
                        service=perm_svc,
                    )
                    if decision.status not in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED):
                        return SandboxResult(
                            request_id=request.id,
                            status=SandboxStatus.BLOCKED,
                            exit_code=126,
                            stderr=f"Blocked by permissions gate (FS_WRITE): {decision.reason or 'Approval required'}",
                        )

                # Intercept privileged code / shell command execution
                is_shell = request.language.lower() in ("shell", "bash", "sh", "cmd", "powershell")
                exec_action = ActionType.EXEC_COMMAND if is_shell else ActionType.EXEC_CODE
                decision = check_permission(
                    exec_action,
                    resource=request.code[:100],
                    project_id=request.project_id,
                    service=perm_svc,
                )
                if decision.status not in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED):
                    return SandboxResult(
                        request_id=request.id,
                        status=SandboxStatus.BLOCKED,
                        exit_code=126,
                        stderr=f"Blocked by permissions gate ({exec_action.value}): {decision.reason or 'Approval required'}",
                    )
            except ImportError:
                pass

        # Create an isolated temporary workspace directory
        temp_scratch = tempfile.mkdtemp(prefix=f"pheonix_sb_{request.project_id}_")

        try:
            result = self.runner.execute(request, scratch_dir=temp_scratch)
            if raise_on_timeout and result.status == SandboxStatus.TIMEOUT:
                raise SandboxTimeoutError(result.stderr or "Sandbox execution timed out")
            return result
        finally:
            # Deterministic post-execution cleanup: wipe scratchpad completely
            try:
                shutil.rmtree(temp_scratch, ignore_errors=True)
            except Exception:
                pass

    def execute(
        self,
        code: str,
        timeout_seconds: Optional[float] = None,
        language: str = "python",
        raise_on_timeout: bool = True,
        permission_service: Optional[Any] = None,
    ) -> SandboxResult:
        """Convenience method to execute code with optional timeout and automatic SandboxTimeoutError."""
        limits = ResourceLimits()
        if timeout_seconds is not None:
            limits.timeout_seconds = timeout_seconds

        req = ExecutionRequest(
            language=language,
            code=code,
            limits=limits,
        )
        return self.run(
            req,
            raise_on_timeout=raise_on_timeout,
            permission_service=permission_service,
        )

    async def run_command(
        self,
        command: str,
        project_id: str = "default",
        timeout_seconds: Optional[float] = None,
    ) -> SandboxResult:
        """Asynchronously executes a shell command within the canonical sandbox with security governance & permissions."""
        import asyncio
        limits = ResourceLimits()
        if timeout_seconds is not None:
            limits.timeout_seconds = timeout_seconds
        req = ExecutionRequest(
            project_id=project_id,
            language="shell",
            code=command,
            limits=limits,
        )
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self.run(req))
        except RuntimeError:
            return self.run(req)

    async def execute_command(
        self,
        command: str,
        config: Optional[Any] = None,
        cwd: Optional[str] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Asynchronous execution interface compatible with agent sandbox adapters."""
        timeout = getattr(config, "timeout_seconds", 30.0) if config else 30.0
        res = await self.run_command(command, project_id=project_id, timeout_seconds=timeout)
        if res.status == SandboxStatus.BLOCKED:
            from agent.core.exceptions import SandboxExecutionError
            raise SandboxExecutionError(
                f"Command blocked by sandbox security policy: '{command}' ({res.stderr})",
                details={"blocked_command": command, "stderr": res.stderr}
            )
        if res.status == SandboxStatus.TIMEOUT:
            from agent.core.exceptions import SandboxExecutionError
            raise SandboxExecutionError(f"Command timed out after {timeout} seconds: '{command}'")
        return {
            "exit_code": res.exit_code,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "execution_time_ms": res.duration_ms,
            "provider": getattr(self.runner, "__class__", type(self.runner)).__name__,
            "status": res.status.value,
        }

