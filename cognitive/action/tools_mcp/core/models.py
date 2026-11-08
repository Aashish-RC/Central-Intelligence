"""Data models for Tool & MCP Registry: Tool Definitions, Invocations, Results, and On-Demand Auth."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolType(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    CONNECTOR = "connector"
    CUSTOM = "custom"


class CredentialStatus(str, Enum):
    UNCONFIGURED = "unconfigured"
    REQUESTED = "requested"
    ACTIVE = "active"
    EXPIRED = "expired"


class ToolParameter(BaseModel):
    """Specification for a single tool argument."""
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


class ToolDefinition(BaseModel):
    """Declarative metadata for a registered tool or MCP method."""
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    tool_type: ToolType = ToolType.BUILTIN
    parameters: List[ToolParameter] = Field(default_factory=list)
    requires_auth: bool = False
    credential_name: Optional[str] = None
    is_idle: bool = True
    call_count: int = 0

    def to_json_schema(self) -> Dict[str, Any]:
        """Converts tool parameters into standard OpenAPI/JSONSchema format for LLM function calling."""
        props = {}
        required = []
        for p in self.parameters:
            props[p.name] = {
                "type": p.type,
                "description": p.description,
            }
            if p.default is not None:
                props[p.name]["default"] = p.default
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }


class AuthRequest(BaseModel):
    """An on-demand credential request enqueued when an unauthenticated connector is invoked."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    credential_name: str
    status: CredentialStatus = CredentialStatus.REQUESTED
    requested_at: datetime = Field(default_factory=utc_now)


class ToolInvocation(BaseModel):
    """An execution call payload targeting a specific tool."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    project_id: str = "default"
    actor_id: str = "agent"


class ToolResult(BaseModel):
    """Output state captured from tool invocation."""
    model_config = ConfigDict(extra="ignore")

    invocation_id: str
    tool_name: str
    success: bool = True
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    auth_required: bool = False
