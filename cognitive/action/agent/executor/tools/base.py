"""Unified Tool Execution Interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolContext(BaseModel):
    """Contextual metadata passed to a tool during invocation."""

    agent_id: str
    run_id: str
    step_number: int = 1
    session_id: Optional[str] = None
    namespace: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Normalized result returned from tool execution."""

    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_summary_str(self) -> str:
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    """Abstract Base Class for all agent tools."""

    name: str
    description: str
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool with given parameters and context."""
        pass
