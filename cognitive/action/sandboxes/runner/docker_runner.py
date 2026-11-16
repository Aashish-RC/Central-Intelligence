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
        container_bin: Optional[str] = None,
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
        self.container_bin = container_bin or os.getenv("CONTAINER_RUNTIME") or "docker"
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        """Check whether container runtime (Docker or Podman) CLI is installed and daemon is responsive."""
        if self._docker_available is True:
            return True

        bin_name = self.container_bin
        bin_path = shutil.which(bin_name)
        if not bin_path:
            # Fall back to podman if docker is not installed
            if bin_name == "docker" and shutil.which("podman"):
                bin_name = "podman"
                self.container_bin = "podman"
                bin_path = shutil.which("podman")
            else:
                self._docker_available = False
                return False

        try:
            res = subprocess.run(
                [bin_name, "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15.0,
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
        """Construct the exact Docker/Podman CLI command for a request based on language."""
        c_name = container_name or f"pheonix-sb-{uuid.uuid4().hex[:12]}"
        
        # Effective resource limits
        mem_limit = f"{request.limits.max_memory_mb}m" if (request.limits and request.limits.max_memory_mb) else self.memory
        if not mem_limit.endswith("m") and not mem_limit.endswith("g"):
            mem_limit = f"{mem_limit}m"

        cpu_limit = self.cpus
        if request.limits and getattr(request.limits, "max_cpu_percent", None):
            cpu_val = request.limits.max_cpu_percent / 100.0
            cpu_limit = f"{cpu_val:.1f}"

        pids_limit = str(request.limits.max_processes if (request.limits and request.limits.max_processes) else 32)
        net_mode = "bridge" if (request.limits and request.limits.network_access) else self.network

        cmd: List[str] = [
            self.container_bin, "run", "--rm", "-i",
            "--name", c_name,
            "--network", net_mode,
            f"--memory={mem_limit}",
            f"--cpus={cpu_limit}",
            "--pids-limit", pids_limit,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--label", f"tenant={request.tenant_id}",
            "--label", f"project={request.project_id}",
        ]

        if scratch_dir:
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
                tenant_id=request.tenant_id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=err or "Execution blocked by security policy",
            )

        # 2. Check Docker availability when running real commands
        if self.command_runner == subprocess.run and not self.is_docker_available():
            return SandboxResult(
                request_id=request.id,
                tenant_id=request.tenant_id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=(
                    "Hardened container execution (Docker) is unavailable. "
                    "Untrusted host execution is strictly prohibited across all environments."
                ),
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
                tenant_id=request.tenant_id,
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
                tenant_id=request.tenant_id,
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
                tenant_id=request.tenant_id,
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
