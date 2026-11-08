"""Docker Container Executor for Sandboxes.

Executes untrusted code inside an isolated container with:
- python:3.12-slim
- no network access (--network none)
- 512 MB memory limit (--memory 512m)
- 1 CPU core allocation (--cpus 1.0)
- read-only root filesystem (--read-only)
- tmpfs /tmp mount (--tmpfs /tmp:rw,noexec,nosuid,size=64m)
- termination after SANDBOX_TIMEOUT_SECONDS (default 30)
- returns stdout, stderr, and exit code
"""

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core.interfaces import BaseDeviceRunner
from ..core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
)
from ..governor.security_governor import SecurityGovernor


class DockerRunner(BaseDeviceRunner):
    """Executes sandboxed scripts inside a hardened Docker container."""

    def __init__(
        self,
        governor: Optional[SecurityGovernor] = None,
        image: str = "python:3.12-slim",
        memory: str = "512m",
        cpus: str = "1.0",
        network: str = "none",
        timeout_seconds: Optional[float] = None,
        command_runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
    ):
        self.governor = governor or SecurityGovernor()
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.network = network
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30.0"))
        )
        self.command_runner = command_runner or subprocess.run
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        """Check whether Docker CLI is installed and the daemon is responsive."""
        if self._docker_available is not None:
            return self._docker_available

        docker_bin = shutil.which("docker")
        if not docker_bin:
            self._docker_available = False
            return False

        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            )
            self._docker_available = (res.returncode == 0)
        except Exception:
            self._docker_available = False

        return self._docker_available

    def build_command(
        self,
        request: ExecutionRequest,
        container_name: Optional[str] = None,
        scratch_dir: Optional[str] = None,
    ) -> List[str]:
        """Construct the exact Docker CLI command for a request based on language."""
        c_name = container_name or f"pheonix-sb-{uuid.uuid4().hex[:12]}"
        cmd: List[str] = [
            "docker", "run", "--rm", "-i",
            "--name", c_name,
            "--network", self.network,
            f"--memory={self.memory}",
            f"--cpus={self.cpus}",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
        ]

        if scratch_dir and request.files:
            scratch_path = Path(scratch_dir).resolve()
            cmd.extend(["-v", f"{str(scratch_path)}:/workspace:ro", "-w", "/workspace"])

        is_shell = request.language.lower() in ("shell", "bash", "sh", "cmd", "powershell")
        if is_shell:
            cmd.extend([self.image, "sh", "-c", request.code])
        else:
            cmd.extend([self.image, "python", "-B", "-"])

        return cmd

    def execute(
        self,
        request: ExecutionRequest,
        scratch_dir: Optional[str] = None,
    ) -> SandboxResult:
        """Execute the request inside an isolated Docker container."""
        # 1. Security governor validation
        is_valid, err = self.governor.validate_request(request)
        if not is_valid:
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=err or "Execution blocked by security policy",
            )

        # 2. Check Docker availability when running real commands
        if self.command_runner == subprocess.run and not self.is_docker_available():
            if os.getenv("SANDBOX_ALLOW_LOCAL") == "1":
                from .local_process_runner import LocalProcessRunner
                return LocalProcessRunner(self.governor).execute(request, scratch_dir or "")
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr="Docker is not available and local execution is disabled; set SANDBOX_ALLOW_LOCAL=1 to allow.",
            )

        container_name = f"pheonix-sb-{uuid.uuid4().hex[:12]}"

        # Optional scratch directory / virtual files mount (read-only)
        if scratch_dir and request.files:
            scratch_path = Path(scratch_dir).resolve()
            scratch_path.mkdir(parents=True, exist_ok=True)
            for filename, content in request.files.items():
                file_path = scratch_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")

        cmd = self.build_command(request, container_name=container_name, scratch_dir=scratch_dir)

        is_shell = request.language.lower() in ("shell", "bash", "sh", "cmd", "powershell")
        stdin_input = None if is_shell else request.code

        # Determine effective timeout
        timeout = (
            request.limits.timeout_seconds
            if request.limits and request.limits.timeout_seconds
            else self.timeout_seconds
        )

        start_time = time.perf_counter()
        try:
            res = self.command_runner(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            status = (
                SandboxStatus.SUCCESS
                if res.returncode == 0
                else SandboxStatus.FAILED
            )

            stdout = res.stdout or ""
            stderr = res.stderr or ""
            max_bytes = request.limits.max_output_bytes
            if len(stdout.encode("utf-8")) > max_bytes:
                stdout = stdout[: max_bytes // 2] + "\n...[OUTPUT TRUNCATED BY SANDBOX RESOURCE LIMIT]..."

            return SandboxResult(
                request_id=request.id,
                status=status,
                exit_code=res.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=round(duration_ms, 2),
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            # Ensure container is terminated
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5.0,
                )
            except Exception:
                pass

            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.TIMEOUT,
                exit_code=-1,
                stdout=getattr(exc, "stdout", "") or "",
                stderr=f"Sandbox execution timed out after {timeout} seconds",
                duration_ms=round(duration_ms, 2),
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=f"Docker sandbox execution error: {str(exc)}",
                duration_ms=round(duration_ms, 2),
            )

    def run_python(
        self,
        code: str,
        limits: Optional[ResourceLimits] = None,
        files: Optional[Dict[str, str]] = None,
        scratch_dir: Optional[str] = None,
    ) -> SandboxResult:
        """Convenience method for running Python code."""
        req = ExecutionRequest(
            language="python",
            code=code,
            limits=limits or ResourceLimits(),
            files=files or {},
        )
        return self.execute(req, scratch_dir=scratch_dir)

    def run_shell(
        self,
        command: str,
        limits: Optional[ResourceLimits] = None,
        files: Optional[Dict[str, str]] = None,
        scratch_dir: Optional[str] = None,
    ) -> SandboxResult:
        """Convenience method for running Shell commands."""
        req = ExecutionRequest(
            language="shell",
            code=command,
            limits=limits or ResourceLimits(),
            files=files or {},
        )
        return self.execute(req, scratch_dir=scratch_dir)
