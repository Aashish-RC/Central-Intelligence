"""Tool Registry: Curated catalog with idle-until-needed tracking and JSONSchema generation."""

import threading
from typing import Any, Dict, List, Optional
from ..core.interfaces import BaseToolRegistry
from ..core.models import ToolDefinition
from .builtin_tools import BUILTIN_TOOL_DEFS


class ToolRegistry(BaseToolRegistry):
    """Central catalog managing registered tools, MCP endpoints, and idle state."""

    def __init__(self, include_builtins: bool = True):
        self._lock = threading.Lock()
        self._tools: Dict[str, ToolDefinition] = {}

        if include_builtins:
            for b_def in BUILTIN_TOOL_DEFS:
                self.register_tool(b_def)

    def register_tool(self, tool: ToolDefinition) -> None:
        with self._lock:
            self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        with self._lock:
            return list(self._tools.values())

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [tool.to_json_schema() for tool in self._tools.values()]

    def mark_used(self, name: str) -> None:
        """Transitions a tool out of the idle state and increments invocation stats."""
        with self._lock:
            tool = self._tools.get(name)
            if tool:
                tool.is_idle = False
                tool.call_count += 1

    def get_idle_tools(self) -> List[ToolDefinition]:
        """Returns tools that are registered but have not yet been activated/invoked."""
        with self._lock:
            return [t for t in self._tools.values() if t.is_idle]
