"""E2B Cloud Code Interpreter and Docker Local Container Execution Engines."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from .interfaces import BaseDeviceRunner
from .models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
    SandboxTimeoutError,
)
from ..governor.security_governor import SecurityGovernor
from ..runner.local_process_runner import LocalProcessRunner


class DockerExecutionEngine(BaseDeviceRunner):
    """Executes sandboxed scripts inside an isolated local Docker container with memory caps and timeouts."""

    def __init__(
        self,
        image: str = "python:3.11-slim",
        governor: Optional[SecurityGovernor] = None,
        fallback_runner: Optional[BaseDeviceRunner] = None,
    ):
        self.image = image
        self.governor = governor or SecurityGovernor()
        self._fallback_runner = fallback_runner or LocalProcessRunner(self.governor)
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        if self._docker_available is not None:
            return self._docker_available

        docker_path = shutil.which("docker")
        if not docker_path:
            self._docker_available = False
            return False

        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3.0,
            )
            self._docker_available = (res.returncode == 0)
        except Exception:
            self._docker_available = False

        return self._docker_available

    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        if not self.is_docker_available():
            return self._fallback_runner.execute(request, scratch_dir)

        scratch_path = Path(scratch_dir).resolve()
        scratch_path.mkdir(parents=True, exist_ok=True)

        # Write files into scratch_dir
        for filename, content in request.files.items():
            fp = scratch_path / filename
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")

        entry_script = scratch_path / "sandbox_entry.py"
        entry_script.write_text(request.code, encoding="utf-8")

        memory_mb = request.limits.max_memory_mb
        timeout = request.limits.timeout_seconds
        start_time = time.perf_counter()

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{str(scratch_path)}:/workspace",
            "-w", "/workspace",
            f"--memory={memory_mb}m",
            "--cpus=1.0",
        ]
        if not request.limits.network_access:
            cmd.extend(["--network", "none"])

        cmd.extend([self.image, "python", "sandbox_entry.py"])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            status = SandboxStatus.SUCCESS if proc.returncode == 0 else SandboxStatus.FAILED
            return SandboxResult(
                request_id=request.id,
                status=status,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=round(duration_ms, 2),
                memory_used_mb=float(memory_mb),
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.TIMEOUT,
                exit_code=-1,
                stdout="",
                stderr=f"Sandbox execution timed out after {timeout} seconds",
                duration_ms=round(duration_ms, 2),
            )
        except Exception:
            return self._fallback_runner.execute(request, scratch_dir)


class E2BExecutionEngine(BaseDeviceRunner):
    """Executes sandboxed scripts in an E2B Cloud Sandbox with fallback to Docker or Local execution."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        template: str = "base",
        governor: Optional[SecurityGovernor] = None,
        fallback_runner: Optional[BaseDeviceRunner] = None,
    ):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.template = template
        self.governor = governor or SecurityGovernor()
        self._fallback_runner = fallback_runner or DockerExecutionEngine(
            governor=self.governor
        )

    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        if self.api_key:
            try:
                import importlib
                e2b_mod = importlib.import_module("e2b_code_interpreter")
                code_interpreter_cls = getattr(e2b_mod, "CodeInterpreter", None)

                if code_interpreter_cls:
                    start_time = time.perf_counter()
                    timeout = request.limits.timeout_seconds
                    with code_interpreter_cls(api_key=self.api_key) as sandbox:
                        # Upload any requested files
                        for filename, content in request.files.items():
                            sandbox.files.write(filename, content)

                        execution = sandbox.notebook.exec_cell(
                            request.code,
                            timeout=timeout,
                        )
                        duration_ms = (time.perf_counter() - start_time) * 1000.0

                        if execution.error:
                            return SandboxResult(
                                request_id=request.id,
                                status=SandboxStatus.FAILED,
                                exit_code=1,
                                stdout="\n".join([str(l) for l in execution.logs.stdout]),
                                stderr=f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}",
                                duration_ms=round(duration_ms, 2),
                            )

                        stdout = "\n".join([str(l) for l in execution.logs.stdout])
                        return SandboxResult(
                            request_id=request.id,
                            status=SandboxStatus.SUCCESS,
                            exit_code=0,
                            stdout=stdout,
                            stderr="\n".join([str(l) for l in execution.logs.stderr]),
                            duration_ms=round(duration_ms, 2),
                        )
            except TimeoutError:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return SandboxResult(
                    request_id=request.id,
                    status=SandboxStatus.TIMEOUT,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Sandbox execution timed out after {request.limits.timeout_seconds} seconds",
                    duration_ms=round(duration_ms, 2),
                )
            except Exception:
                pass

        # Fallback to local Docker or Process runner
        return self._fallback_runner.execute(request, scratch_dir)
