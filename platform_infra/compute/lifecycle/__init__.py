"""Model Lifecycle, Capability Activation and Zero-Downtime Hot-Swap subsystem (L16 Compute)."""

from .hot_swap import (
    ModelHotSwapManager,
    ModelExecutionHandle,
    SwapEvent,
)
from .capability_activation import (
    CapabilityActivationManager,
    CapabilityDefinition,
    CapabilityState,
    CapabilityLease,
    TenantResourceAccounting,
    InsufficientResourceError,
    CapabilityDependencyError,
    CapabilityActivationError,
    RuntimeAdapter,
    SimulatedRuntimeAdapter,
    DockerComposeRuntimeAdapter,
    detect_system_memory_limit_mb,
)

__all__ = [
    "ModelHotSwapManager",
    "ModelExecutionHandle",
    "SwapEvent",
    "CapabilityActivationManager",
    "CapabilityDefinition",
    "CapabilityState",
    "CapabilityLease",
    "TenantResourceAccounting",
    "InsufficientResourceError",
    "CapabilityDependencyError",
    "CapabilityActivationError",
    "RuntimeAdapter",
    "SimulatedRuntimeAdapter",
    "DockerComposeRuntimeAdapter",
    "detect_system_memory_limit_mb",
]
