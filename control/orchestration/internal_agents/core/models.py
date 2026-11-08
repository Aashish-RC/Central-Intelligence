"""Core data models for Internal Agents: Health, Safety Audits, Resource Telemetry, and Visible Logs."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentType(str, Enum):
    PROVIDER_HEALTH = "provider_health"
    GUARDRAIL_REVIEW = "guardrail_review"
    RESOURCE_MONITOR = "resource_monitor"


class AgentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthCheckResult(BaseModel):
    """Result of a diagnostic health ping against an LLM provider."""
    model_config = ConfigDict(extra="ignore")

    provider: str
    is_healthy: bool = True
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    checked_at: datetime = Field(default_factory=utc_now)


class SafetyAuditFinding(BaseModel):
    """A policy or safety anomaly flagged during conversation transcript audits."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    category: str = "injection_attempt"
    severity: AgentSeverity = AgentSeverity.WARNING
    details: str = ""
    context_snippet: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class ResourceMetric(BaseModel):
    """Device compute, memory, and task load telemetry snapshot."""
    model_config = ConfigDict(extra="ignore")

    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_percent: float = 0.0
    active_tasks: int = 0
    recorded_at: datetime = Field(default_factory=utc_now)


class AgentLogEntry(BaseModel):
    """An individual entry in the human-visible audit log stream."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    severity: AgentSeverity = AgentSeverity.INFO
    action: str = ""
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class AgentRunReport(BaseModel):
    """Summary outcome of a scheduled or manual agent execution cycle."""
    model_config = ConfigDict(extra="ignore")

    agent_type: AgentType
    success: bool = True
    items_processed: int = 0
    anomalies_detected: int = 0
    duration_ms: float = 0.0
    summary: str = ""
    completed_at: datetime = Field(default_factory=utc_now)
