"""Local Process Runner: Resource-governed subprocess execution with timeouts and output bounds."""

import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict
from ..core.interfaces import BaseDeviceRunner
from ..core.models import ExecutionRequest, SandboxResult, SandboxStatus
from ..governor.security_governor import SecurityGovernor


class LocalProcessRunner(BaseDeviceRunner):
    """Executes sandboxed scripts in a guarded local subprocess environment."""

    def __init__(self, governor: SecurityGovernor):
        self.governor = governor

    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        if os.getenv("SANDBOX_ALLOW_LOCAL") != "1":
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr="Local subprocess execution disallowed; set SANDBOX_ALLOW_LOCAL=1 to allow.",
            )

        scratch_path = Path(scratch_dir).resolve()
        scratch_path.mkdir(parents=True, exist_ok=True)

        # Write any virtual input files into scratchpad
        for filename, content in request.files.items():
            file_path = scratch_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        # Sanitize environment
        env = self.governor.sanitize_environment(
            allowed_vars=request.limits.allow_env_vars,
            custom_env=request.environment,
        )

        # Build command based on language
        if request.language.lower() == "python":
            script_file = scratch_path / "sandbox_entry.py"
            script_file.write_text(request.code, encoding="utf-8")
            cmd = [sys.executable, str(script_file)]
            use_shell = False
        else:
            cmd = request.code
            use_shell = True

        start_time = time.perf_counter()
        timeout = request.limits.timeout_seconds
        max_bytes = request.limits.max_output_bytes

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(scratch_path),
                env=env,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                # Truncate output if exceeding limits
                if len(stdout.encode("utf-8")) > max_bytes:
                    stdout = stdout[: max_bytes // 2] + "\n...[OUTPUT TRUNCATED BY SANDBOX RESOURCE LIMIT]..."

                status = SandboxStatus.SUCCESS if proc.returncode == 0 else SandboxStatus.FAILED

                return SandboxResult(
                    request_id=request.id,
                    status=status,
                    exit_code=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=round(duration_ms, 2),
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return SandboxResult(
                    request_id=request.id,
                    status=SandboxStatus.TIMEOUT,
                    exit_code=-1,
                    stdout=stdout,
                    stderr=f"Sandbox execution timed out after {timeout} seconds",
                    duration_ms=round(duration_ms, 2),
                )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=f"Sandbox execution error: {str(e)}",
                duration_ms=round(duration_ms, 2),
            )
