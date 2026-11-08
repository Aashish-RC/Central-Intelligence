"""
Pheonix Rules Layer Data Models & Types
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RuleScope(str, Enum):
    GLOBAL = "global"
    GATEWAY = "model-gateway"
    AGENT = "agent"
    MEMORY = "memory"
    TOOLS = "tools"


class RuleAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REWRITE = "rewrite"
    NOTIFY = "notify"
    AUDIT = "audit"


class RuleCondition(BaseModel):
    field: str  # e.g., "provider", "model", "max_tokens", "prompt_length"
    operator: str  # "==", "!=", ">", "<", ">=", "<=", "in", "not_in", "contains"
    value: Any


class RuleDefinition(BaseModel):
    rule_id: str
    name: str
    scope: RuleScope = RuleScope.GLOBAL
    conditions: List[RuleCondition] = Field(default_factory=list)
    action: RuleAction = RuleAction.BLOCK
    priority: int = 100  # Lower number = higher priority (0 to 1000)
    enabled: bool = True
    message: Optional[str] = None
    rewrite_payload: Optional[Dict[str, Any]] = None
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class RuleEvaluationResult(BaseModel):
    allowed: bool
    action: RuleAction
    matched_rule: Optional[RuleDefinition] = None
    reason: Optional[str] = None
    rewritten_context: Optional[Dict[str, Any]] = None


class RuleChangeEvent(BaseModel):
    event_type: str  # "CREATED", "UPDATED", "DELETED", "TOGGLED"
    rule: RuleDefinition
    timestamp: float = Field(default_factory=time.time)
