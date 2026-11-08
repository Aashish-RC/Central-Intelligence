"""Standard exception hierarchy for the Agent Layer."""


class AgentLayerError(Exception):
    """Base exception for all agent layer errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ManifestValidationError(AgentLayerError):
    """Raised when an AgentManifest fails validation against schema or constraints."""
    pass


class ToolExecutionError(AgentLayerError):
    """Raised when a tool fails to execute or returns an invalid payload."""
    pass


class SandboxExecutionError(AgentLayerError):
    """Raised when sandbox execution fails, times out, or encounters a security block."""
    pass


class GuardrailViolationError(AgentLayerError):
    """Raised when prompt or response violates safety, compliance, or brand guidelines."""
    pass


class MemoryAccessError(AgentLayerError):
    """Raised when read or write operations to the fused memory layer fail."""
    pass


class RunnerExecutionError(AgentLayerError):
    """Raised when an agent execution loop encounters an unrecoverable failure."""
    pass
