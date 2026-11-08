"""Core data models for Pheonix Agent Builder."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentPersona(BaseModel):
    role: str
    tone: str = "concise and analytical"
    expertise_areas: List[str] = Field(default_factory=list)
    operational_constraints: List[str] = Field(default_factory=list)


class AgentModelBinding(BaseModel):
    primary_model: str = "openai/gpt-4o"
    fallback_model: str = "anthropic/claude-3-5-sonnet"
    temperature: float = 0.2
    max_tokens: int = 4096


class AgentToolBinding(BaseModel):
    tool_ids: List[str] = Field(default_factory=list)
    mcp_server_ids: List[str] = Field(default_factory=list)
    consequential_tools: List[str] = Field(default_factory=list)
    missing_tools: List[str] = Field(default_factory=list)


class AgentRulesBinding(BaseModel):
    permission_mode: str = "ask_on_changes"
    active_rules: List[str] = Field(default_factory=list)
    sandbox_required: bool = True
    max_cost_per_run_usd: float = 1.0


class AgentSpecification(BaseModel):
    agent_id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str
    version: str = "0.1.0"
    description: str
    persona: AgentPersona
    system_prompt: str
    model_binding: AgentModelBinding = Field(default_factory=AgentModelBinding)
    tool_binding: AgentToolBinding = Field(default_factory=AgentToolBinding)
    rules_binding: AgentRulesBinding = Field(default_factory=AgentRulesBinding)
    memory_enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class DescribeAgentRequest(BaseModel):
    prompt: str
    target_domain: Optional[str] = None
    requested_permission_mode: Optional[str] = None
    sandbox_preferred: bool = True


class AgentBuildResult(BaseModel):
    success: bool
    specification: Optional[AgentSpecification] = None
    compile_duration_ms: float = 0.0
    compiler_notes: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


class AgentExecutionResult(BaseModel):
    agent_id: str
    prompt: str
    response_text: str
    tools_invoked: List[str] = Field(default_factory=list)
    status: str = "completed"
    duration_ms: float = 0.0
