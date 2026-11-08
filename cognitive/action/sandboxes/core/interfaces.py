"""Abstract interfaces for Security Governor, Device Runner, and Sandbox Manager."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from .models import ExecutionRequest, SandboxResult


class BaseSecurityGovernor(ABC):
    """Enforces static security policies and environment sanitization."""

    @abstractmethod
    def validate_request(self, request: ExecutionRequest) -> Tuple[bool, Optional[str]]:
        """Validates that code and request params do not violate security blocklists."""
        pass

    @abstractmethod
    def sanitize_environment(
        self, allowed_vars: List[str], custom_env: Dict[str, str]
    ) -> Dict[str, str]:
        """Filters host environment variables to prevent secret leakage."""
        pass


class BaseDeviceRunner(ABC):
    """Executes sandboxed code in a designated directory."""

    @abstractmethod
    def execute(self, request: ExecutionRequest, scratch_dir: str) -> SandboxResult:
        """Runs the execution request and captures resource-governed outputs."""
        pass


class BaseSandboxManager(ABC):
    """Manages isolated scratchpad lifecycles and orchestrates execution."""

    @abstractmethod
    def run(self, request: ExecutionRequest) -> SandboxResult:
        """Executes the request inside an isolated, disposable scratch directory."""
        pass
