"""Tool Dispatcher: Executes tools with on-demand credential checks, MCP routing, and error capture."""

import time
from typing import Any, Callable, Dict, Optional
from ..auth.on_demand_auth import OnDemandAuthBridge
from ..catalog.builtin_tools import BUILTIN_HANDLERS
from ..catalog.registry import ToolRegistry
from ..core.models import ToolInvocation, ToolResult, ToolType
from ..mcp.client import MCPClient


class ToolDispatcher:
    """Executes tools with idle-until-needed credential resolution and MCP routing."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        auth_bridge: Optional[OnDemandAuthBridge] = None,
        mcp_client: Optional[MCPClient] = None,
    ):
        self.registry = registry or ToolRegistry()
        self.auth_bridge = auth_bridge or OnDemandAuthBridge()
        self.mcp_client = mcp_client or MCPClient()
        self._custom_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register_custom_handler(self, tool_name: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register execution logic for custom connectors or local handlers."""
        self._custom_handlers[tool_name] = handler

    def dispatch(self, invocation: ToolInvocation) -> ToolResult:
        """Dispatches a tool invocation, validating on-demand credentials and routing appropriately."""
        start_time = time.perf_counter()
        tool = self.registry.get_tool(invocation.tool_name)

        if not tool:
            return ToolResult(
                invocation_id=invocation.id,
                tool_name=invocation.tool_name,
                success=False,
                error=f"Tool '{invocation.tool_name}' is not registered in the catalog",
            )

        # Mark tool as active (idle-until-needed transition)
        self.registry.mark_used(tool.name)

        # On-Demand Credential Check: Ask for credentials strictly when used
        if tool.requires_auth and tool.credential_name:
            if not self.auth_bridge.has_credential(tool.credential_name):
                # Request credentials on-demand and enqueue
                auth_req = self.auth_bridge.request_credential(tool.name, tool.credential_name)
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return ToolResult(
                    invocation_id=invocation.id,
                    tool_name=tool.name,
                    success=False,
                    auth_required=True,
                    error=f"Connector '{tool.name}' requires credential '{tool.credential_name}' (Request ID: {auth_req.id}). Enqueued in auth queue.",
                    duration_ms=round(duration_ms, 2),
                )

        try:
            # Route to appropriate backend
            if tool.tool_type == ToolType.BUILTIN:
                handler = BUILTIN_HANDLERS.get(tool.name) or self._custom_handlers.get(tool.name)
                if not handler:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return ToolResult(
                        invocation_id=invocation.id,
                        tool_name=tool.name,
                        success=False,
                        error=f"Built-in handler for '{tool.name}' is not registered",
                        duration_ms=round(duration_ms, 2),
                    )
                output = handler(invocation.arguments)

            elif tool.tool_type == ToolType.MCP:
                output = self.mcp_client.call_mcp_tool(tool.name, invocation.arguments)

            else:
                handler = self._custom_handlers.get(tool.name) or BUILTIN_HANDLERS.get(tool.name)
                if not handler:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return ToolResult(
                        invocation_id=invocation.id,
                        tool_name=tool.name,
                        success=False,
                        error=f"No execution handler registered for '{tool.name}'",
                        duration_ms=round(duration_ms, 2),
                    )
                output = handler(invocation.arguments)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                invocation_id=invocation.id,
                tool_name=tool.name,
                success=True,
                output=output,
                duration_ms=round(duration_ms, 2),
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                invocation_id=invocation.id,
                tool_name=tool.name,
                success=False,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
