"""Curated Tool Registry with Whitelist, Rate Limiting, RBAC, and Schema Validation.

Feature: 5.08 (Curated Tool Registry)
Ensures only verified, administrator-approved tools with strictly validated
schemas and enforceable per-agent rate limits can be invoked by reasoning agents.
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field, ConfigDict


class ToolAccessDeniedError(Exception):
    """Raised when an agent lacks authorization to execute a tool."""
    pass


class ToolRateLimitExceededError(Exception):
    """Raised when an agent or tool exceeds rate limits."""
    pass


class ToolValidationError(Exception):
    """Raised when input parameters fail schema validation."""
    pass


class CuratedToolMetadata(BaseModel):
    """Metadata specification for an administrator-curated tool."""
    model_config = ConfigDict(extra="ignore")

    tool_id: str
    name: str
    category: str = "general"
    description: str = ""
    is_approved: bool = False
    approved_by: Optional[str] = None
    required_roles: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 60
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class CuratedToolRegistry:
    """Enterprise registry for tool curation, access control, and invocation policing."""

    def __init__(self):
        self._tools: Dict[str, CuratedToolMetadata] = {}
        # Key: (tool_id, agent_id), Value: list of epoch timestamps
        self._invocation_history: Dict[Tuple[str, str], List[float]] = {}

    def register_tool(self, tool: CuratedToolMetadata) -> None:
        """Register or update a tool in the catalog."""
        self._tools[tool.tool_id] = tool

    def approve_tool(self, tool_id: str, approver: str) -> None:
        """Grant admin approval to whitelist a tool for agent execution."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise KeyError(f"Tool '{tool_id}' not found in registry")
        tool.is_approved = True
        tool.approved_by = approver

    def revoke_tool(self, tool_id: str, reason: str = "") -> None:
        """Revoke approval for a tool immediately blocking all executions."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise KeyError(f"Tool '{tool_id}' not found in registry")
        tool.is_approved = False
        tool.approved_by = None

    def get_tool(self, tool_id: str) -> Optional[CuratedToolMetadata]:
        """Fetch tool specification."""
        return self._tools.get(tool_id)

    def list_curated_tools(
        self, approved_only: bool = True, role: Optional[str] = None
    ) -> List[CuratedToolMetadata]:
        """List registered tools according to curation status and user roles."""
        tools = list(self._tools.values())
        if approved_only:
            tools = [t for t in tools if t.is_approved]
        if role:
            tools = [t for t in tools if not t.required_roles or role in t.required_roles or "admin" in t.required_roles]
        return tools

    def check_access(
        self, tool_id: str, agent_id: str, agent_roles: List[str]
    ) -> None:
        """Verify tool approval status and agent role permissions."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise ToolAccessDeniedError(f"Tool '{tool_id}' does not exist in registry.")

        if not tool.is_approved:
            raise ToolAccessDeniedError(
                f"Tool '{tool_id}' has not been approved by an administrator."
            )

        if tool.required_roles:
            role_set = set(agent_roles)
            if "admin" not in role_set and not any(r in role_set for r in tool.required_roles):
                raise ToolAccessDeniedError(
                    f"Agent '{agent_id}' lacks required roles: {tool.required_roles}"
                )

    def check_and_record_rate_limit(self, tool_id: str, agent_id: str) -> None:
        """Enforce per-minute sliding window rate limit for an agent and tool."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise KeyError(f"Tool '{tool_id}' not found")

        now = time.time()
        window_start = now - 60.0
        key = (tool_id, agent_id)

        history = self._invocation_history.get(key, [])
        # Evict old invocations outside the 60s window
        active_invocations = [t for t in history if t > window_start]

        if len(active_invocations) >= tool.rate_limit_per_minute:
            raise ToolRateLimitExceededError(
                f"Rate limit exceeded for tool '{tool_id}' by agent '{agent_id}' "
                f"({len(active_invocations)}/{tool.rate_limit_per_minute} rpm)."
            )

        active_invocations.append(now)
        self._invocation_history[key] = active_invocations

    def validate_parameters(self, tool_id: str, params: Dict[str, Any]) -> None:
        """Validate input arguments against tool's parameter schema."""
        tool = self._tools.get(tool_id)
        if not tool:
            raise KeyError(f"Tool '{tool_id}' not found")

        schema = tool.input_schema
        if not schema:
            return  # No explicit schema defined

        # Verify required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in params:
                raise ToolValidationError(
                    f"Missing required parameter '{field}' for tool '{tool_id}'"
                )

        # Basic type checking if properties defined
        properties = schema.get("properties", {})
        for prop_name, prop_spec in properties.items():
            if prop_name in params:
                val = params[prop_name]
                expected_type = prop_spec.get("type")
                if expected_type == "string" and not isinstance(val, str):
                    raise ToolValidationError(
                        f"Field '{prop_name}' must be a string, got {type(val).__name__}"
                    )
                elif expected_type == "integer" and not (isinstance(val, int) and not isinstance(val, bool)):
                    raise ToolValidationError(
                        f"Field '{prop_name}' must be an integer, got {type(val).__name__}"
                    )
                elif expected_type == "boolean" and not isinstance(val, bool):
                    raise ToolValidationError(
                        f"Field '{prop_name}' must be a boolean, got {type(val).__name__}"
                    )
                elif expected_type == "array" and not isinstance(val, list):
                    raise ToolValidationError(
                        f"Field '{prop_name}' must be an array, got {type(val).__name__}"
                    )
