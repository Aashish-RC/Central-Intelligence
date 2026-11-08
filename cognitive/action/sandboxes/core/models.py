"""Data models for Sandboxes: Resource Limits, Execution Requests, and Sandbox Results."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SandboxStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    TERMINATED = "terminated"


import os


class SandboxTimeoutError(TimeoutError):
    """Raised when sandbox execution exceeds configured timeout limit."""
    pass


class ResourceLimits(BaseModel):
    """Enforced computational and security constraints."""
    model_config = ConfigDict(extra="ignore")

    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30.0"))
    )
    max_memory_mb: int = Field(
        default_factory=lambda: int(os.getenv("SANDBOX_MEMORY_MB", "512"))
    )
    max_output_bytes: int = 65536
    network_access: bool = False
    allow_env_vars: List[str] = Field(
        default_factory=lambda: ["PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH"]
    )


class ExecutionRequest(BaseModel):
    """Payload to execute inside the isolated sandbox."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    project_id: str = "default"
    language: str = "python"  # 'python' | 'shell'
    code: str
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    environment: Dict[str, str] = Field(default_factory=dict)
    files: Dict[str, str] = Field(default_factory=dict, description="Relative path -> file content")


class SandboxResult(BaseModel):
    """Output state captured from sandboxed execution."""
    model_config = ConfigDict(extra="ignore")

    request_id: str
    tenant_id: str = "default"
    status: SandboxStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    memory_used_mb: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)
