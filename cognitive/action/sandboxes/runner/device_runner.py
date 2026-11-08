"""Device Runner: Hardware-aware execution selector and sandbox dispatcher."""

from typing import Dict, Optional
from ..core.interfaces import BaseDeviceRunner
from ..core.models import ExecutionRequest, ResourceLimits, SandboxResult
from ..governor.security_governor import SecurityGovernor
from .local_process_runner import LocalProcessRunner


class DeviceRunner(BaseDeviceRunner):
    """Dynamic device runner selecting local process isolation or containerized execution."""

    def __init__(self, governor: Optional[SecurityGovernor] = None):
        self.governor = governor or SecurityGovernor()
        self.local_runner = LocalProcessRunner(self.governor)

    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        # Validate request against security policy first
        is_valid, err = self.governor.validate_request(request)
        if not is_valid:
            from ..core.models import SandboxStatus
            return SandboxResult(
                request_id=request.id,
                status=SandboxStatus.BLOCKED,
                exit_code=-1,
                stderr=err or "Execution blocked by security policy",
            )

        return self.local_runner.execute(request, scratch_dir)

    def run_python(
        self,
        code: str,
        limits: Optional[ResourceLimits] = None,
        files: Optional[Dict[str, str]] = None,
        scratch_dir: str = "./sandbox_scratch",
    ) -> SandboxResult:
        req = ExecutionRequest(
            language="python",
            code=code,
            limits=limits or ResourceLimits(),
            files=files or {},
        )
        return self.execute(req, scratch_dir)

    def run_shell(
        self,
        command: str,
        limits: Optional[ResourceLimits] = None,
        scratch_dir: str = "./sandbox_scratch",
    ) -> SandboxResult:
        req = ExecutionRequest(
            language="shell",
            code=command,
            limits=limits or ResourceLimits(),
        )
        return self.execute(req, scratch_dir)
