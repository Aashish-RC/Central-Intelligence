"""Data models for Layer 5 Action Safety, Risk Classification, and Approval Gates.

Features: 5.22, 5.23, 5.24, 5.27
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    """Categorization of operational risk for planned agent actions."""
    LOW = "low"            # Read-only, cache inspect, harmless queries
    MEDIUM = "medium"      # Temporary scratchpad writes, local drafts
    HIGH = "high"          # External broadcasts, file mutations, code execution
    CRITICAL = "critical"  # Production deploys, financial operations, data destruction


class ActionRiskAssessment(BaseModel):
    """Comprehensive risk profile for an action candidate."""
    model_config = ConfigDict(extra="ignore")

    action_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    action_name: str
    risk_level: RiskLevel
    requires_approval: bool
    reasons: List[str] = Field(default_factory=list)
    affected_targets: List[str] = Field(default_factory=list)
    is_reversible: bool = True
    blast_radius_summary: str = "Local scoped operation"


class ApprovalGateRequest(BaseModel):
    """Request paused pending human or supervisor authorization."""
    model_config = ConfigDict(extra="ignore")

    gate_id: str = Field(default_factory=lambda: f"gate_{uuid.uuid4().hex[:8]}")
    assessment: ActionRiskAssessment
    agent_id: str
    status: str = "pending"  # 'pending' | 'approved' | 'rejected'
    approver: Optional[str] = None
    decision_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class BlastRadiusReport(BaseModel):
    """Dry-run impact simulation report."""
    model_config = ConfigDict(extra="ignore")

    action_name: str
    simulated_at: datetime = Field(default_factory=utc_now)
    affected_files: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    estimated_cost_usd: float = 0.0
    is_destructive: bool = False
    reversibility_guaranteed: bool = True
    summary: str
