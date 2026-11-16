"""Local Process Runner: Resource-governed subprocess execution with timeouts and output bounds."""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Dict, Optional
from ..core.interfaces import BaseDeviceRunner
from ..core.models import ExecutionRequest, SandboxResult, SandboxStatus
from ..governor.security_governor import SecurityGovernor
from control.safety.production_guard import is_production


class LocalProcessRunner(BaseDeviceRunner):
    """Executes sandboxed scripts in a guarded local subprocess environment."""

    def __init__(self, governor: Optional[SecurityGovernor] = None):
        self.governor = governor or SecurityGovernor()

    def _apply_windows_job_limits(self, pid: int, max_memory_mb: Optional[int] = None) -> Optional[int]:
        """Applies Windows Job Object memory and lifecycle ceilings to process (DEF-03 / Task C4)."""
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32

            PROCESS_ALL_ACCESS = 0x1F0FFF
            h_proc = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not h_proc:
                return None

            h_job = kernel32.CreateJobObjectW(None, None)
            if not h_job:
                kernel32.CloseHandle(h_proc)
                return None

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            JobObjectExtendedLimitInformation = 9
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if max_memory_mb and max_memory_mb > 0:
                flags |= JOB_OBJECT_LIMIT_JOB_MEMORY
                info.JobMemoryLimit = int(max_memory_mb * 1024 * 1024)

            info.BasicLimitInformation.LimitFlags = flags

            success = kernel32.SetInformationJobObject(
                h_job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )

            if success:
                kernel32.AssignProcessToJobObject(h_job, h_proc)

            kernel32.CloseHandle(h_proc)
            return h_job
        except Exception:
            return None

    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        # 1. Host execution is unconditionally forbidden in production
        if is_production():
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr="Host subprocess execution is strictly forbidden in production.",
            )

        # 2. Establish single trust boundary: untrusted commands must never execute on host
        trusted_ctx = getattr(request, "trusted_context", None)
        if not trusted_ctx:
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=(
                    "Untrusted command execution on the host machine is strictly prohibited across all environments. "
                    "Hardened container isolation (Docker/E2B) is mandatory."
                ),
            )

        # 3. For requests with explicit trusted context, validate against policy
        from ..trusted_host import TrustedHostExecutionPolicy, TrustedHostExecutionError
        policy = TrustedHostExecutionPolicy()
        try:
            policy.validate_context(trusted_ctx)
        except TrustedHostExecutionError as auth_err:
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=f"Host execution rejected by security policy: {auth_err}",
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

        # Build command based on language (Strictly shell=False to prevent shell injection)
        if request.language.lower() == "python":
            script_file = scratch_path / "sandbox_entry.py"
            script_file.write_text(request.code, encoding="utf-8")
            cmd = [sys.executable, str(script_file)]
        else:
            try:
                cmd_args = shlex.split(request.code, posix=(os.name != "nt"))
                if os.name == "nt":
                    cmd = ["cmd.exe", "/c"] + cmd_args
                else:
                    cmd = cmd_args
            except Exception as parse_err:
                return SandboxResult(
                    request_id=request.id,
                    status=SandboxStatus.FAILED,
                    exit_code=-1,
                    stderr=f"Failed to parse command arguments: {parse_err}",
                )

        use_shell = False

        start_time = time.perf_counter()
        timeout = request.limits.timeout_seconds
        max_bytes = request.limits.max_output_bytes

        h_job = None
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

            # Apply OS-level Job Object memory and lifecycle ceilings on Windows (DEF-03 / Task C4)
            if os.name == "nt":
                h_job = self._apply_windows_job_limits(proc.pid, request.limits.max_memory_mb)

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
            finally:
                if h_job and os.name == "nt":
                    try:
                        import ctypes
                        ctypes.windll.kernel32.CloseHandle(h_job)
                    except Exception:
                        pass

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
