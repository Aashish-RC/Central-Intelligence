"""
Pheonix Resource Optimizer Data Models
Defines telemetry signals, adaptive scheduling decisions, and optimizer configuration.
"""

import os
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

Action = Literal["allow", "delay", "reject"]


class Decision(BaseModel):
    """Scheduling decision produced by the ResourceOptimizer."""
    action: Action
    concurrency_cap: int
    delay_seconds: float = 0.0
    reason: str


class ResourceSignals(BaseModel):
    """Host resource metrics and external provider rate-limit telemetry."""
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    gpu_percent: Optional[float] = None
    queue_depth: int = 0
    provider_headroom: Dict[str, float] = Field(default_factory=dict)


class ResourceOptimizerConfig(BaseModel):
    """Configuration settings for adaptive concurrency and safety thresholds."""
    initial_cap: int = 2
    max_cap: int = 8
    healthy_checks_threshold: int = 3
    cpu_threshold_percent: float = 85.0
    ram_threshold_percent: float = 85.0
    provider_headroom_threshold: float = 0.10
    default_delay_seconds: float = 0.5
    lease_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "ResourceOptimizerConfig":
        """Load configuration overrides from environment variables."""
        return cls(
            initial_cap=int(os.getenv("PHEONIX_RESOURCE_INITIAL_CAP", "2")),
            max_cap=int(os.getenv("PHEONIX_RESOURCE_MAX_CAP", "8")),
            healthy_checks_threshold=int(os.getenv("PHEONIX_RESOURCE_HEALTHY_THRESHOLD", "3")),
            cpu_threshold_percent=float(os.getenv("PHEONIX_RESOURCE_CPU_THRESHOLD", "85.0")),
            ram_threshold_percent=float(os.getenv("PHEONIX_RESOURCE_RAM_THRESHOLD", "85.0")),
            provider_headroom_threshold=float(
                os.getenv("PHEONIX_RESOURCE_PROVIDER_HEADROOM_THRESHOLD", "0.10")
            ),
            default_delay_seconds=float(
                os.getenv("PHEONIX_RESOURCE_DEFAULT_DELAY_SECONDS", "0.5")
            ),
            lease_timeout_seconds=float(
                os.getenv("PHEONIX_RESOURCE_LEASE_TIMEOUT_SECONDS", "5.0")
            ),
        )


class TaskDescriptor(BaseModel):
    """Metadata describing a task requesting execution capacity."""
    task_id: str
    provider: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
