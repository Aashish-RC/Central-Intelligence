"""Abstract interfaces for Tool Registry, On-Demand Auth, and MCP Client."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .models import (
    AuthRequest,
    ToolDefinition,
    ToolInvocation,
    ToolResult,
)


class BaseToolRegistry(ABC):
    """Abstract catalog for registering and discovering tools and MCP capabilities."""

    @abstractmethod
    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool in the catalog."""
        pass

    @abstractmethod
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Fetch a tool definition by unique name."""
        pass

    @abstractmethod
    def list_tools(self) -> List[ToolDefinition]:
        """Lists all registered tools."""
        pass

    @abstractmethod
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Returns JSONSchema list for all registered tools."""
        pass


class BaseOnDemandAuth(ABC):
    """Abstract interface for lazy-loaded credential resolution."""

    @abstractmethod
    def has_credential(self, credential_name: str) -> bool:
        """Checks if active credential exists."""
        pass

    @abstractmethod
    def request_credential(self, tool_name: str, credential_name: str) -> AuthRequest:
        """Enqueues an on-demand auth request when an unauthenticated tool is invoked."""
        pass

    @abstractmethod
    def provide_credential(self, credential_name: str, secret_value: str) -> bool:
        """Stores or updates credentials for a connector."""
        pass

    @abstractmethod
    def get_pending_requests(self) -> List[AuthRequest]:
        """Lists active pending credential requests."""
        pass


class BaseMCPClient(ABC):
    """Abstract client for connecting to Model Context Protocol (MCP) servers."""

    @abstractmethod
    def list_mcp_tools(self) -> List[ToolDefinition]:
        """Discovers tools exposed by the MCP server."""
        pass

    @abstractmethod
    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on the MCP server via JSON-RPC."""
        pass
