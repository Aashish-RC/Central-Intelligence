"""
Unified Cross-Module Audit Data Models with Tenant & Role Awareness.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    USER = "user"
    VIEWER = "viewer"
    AGENT = "agent"
    SYSTEM = "system"


class AuditSeverity(str, Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class UnifiedAuditEntry(BaseModel):
    """Immutable audit record spanning all Pheonix modules."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = Field(default="default", description="Tenant isolation boundary")
    project_id: str = Field(default="default", description="Project or workspace boundary")
    user_id: Optional[str] = Field(default=None, description="Actor user ID if applicable")
    role: str = Field(default=UserRole.SYSTEM.value, description="Role of the actor at time of action")
    module: str = Field(..., description="Source module (auth, vault, permissions, sandboxes, memory, etc.)")
    action: str = Field(..., description="Action performed, e.g. secret_read, login, exec_code")
    resource: str = Field(default="", description="Target resource or entity")
    status: str = Field(default="success", description="Outcome: success, failure, denied, blocked")
    severity: AuditSeverity = Field(default=AuditSeverity.INFO, description="Event severity classification")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual payload")
    client_ip: Optional[str] = Field(default=None, description="Client network IP if available")
    timestamp: datetime = Field(default_factory=utc_now, description="Event timestamp in UTC")
