"""Model Context Protocol (MCP) Client: JSON-RPC 2.0 client for tool discovery and invocation."""

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional
from ..core.interfaces import BaseMCPClient
from ..core.models import ToolDefinition, ToolParameter, ToolType


class MCPClient(BaseMCPClient):
    """JSON-RPC 2.0 compliant MCP client supporting tool discovery and execution via local mocks or remote HTTP/SSE."""

    def __init__(
        self,
        server_name: str = "default_mcp_server",
        server_url: Optional[str] = None,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.server_name = server_name
        self.server_url = server_url.rstrip("/") if server_url else None
        self.timeout = timeout
        self.headers = headers or {"Content-Type": "application/json", "Accept": "application/json"}
        self._request_id = 0
        self._mock_tools: Dict[str, Dict[str, Any]] = {}
        self._mock_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a JSON-RPC 2.0 request to the remote MCP HTTP server."""
        if not self.server_url:
            raise ValueError(f"Cannot send JSON-RPC request: server_url is not set on MCPClient '{self.server_name}'.")

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.server_url, data=data, headers=self.headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                res = json.loads(body)
                if "error" in res:
                    err = res["error"]
                    err_msg = err.get("message", "Unknown JSON-RPC error")
                    err_code = err.get("code", -1)
                    raise RuntimeError(f"MCP remote error [{err_code}]: {err_msg}")
                return res.get("result", {})
        except urllib.error.HTTPError as e:
            err_content = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"MCP HTTP {e.code} error: {err_content}") from e
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to connect to MCP server at {self.server_url}: {e.reason}") from e

    def register_mcp_server_mock(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Register an in-memory MCP tool endpoint for testing."""
        self._mock_tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
        self._mock_handlers[name] = handler

    def list_mcp_tools(self) -> List[ToolDefinition]:
        """Discovers tools available on the MCP server via standard 'tools/list' protocol."""
        if self.server_url:
            result = self._send_jsonrpc("tools/list")
            tools_data = result.get("tools", [])
            tool_defs = []
            for t in tools_data:
                params = []
                for p in t.get("parameters", []):
                    if isinstance(p, ToolParameter):
                        params.append(p)
                    elif isinstance(p, dict):
                        params.append(ToolParameter(**p))
                tool_defs.append(
                    ToolDefinition(
                        name=t["name"],
                        description=t.get("description", ""),
                        tool_type=ToolType.MCP,
                        parameters=params,
                    )
                )
            return tool_defs

        tool_defs = []
        for t_info in self._mock_tools.values():
            tool_defs.append(
                ToolDefinition(
                    name=t_info["name"],
                    description=t_info["description"],
                    tool_type=ToolType.MCP,
                    parameters=t_info["parameters"],
                )
            )
        return tool_defs

    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on the MCP server via standard 'tools/call' protocol."""
        if self.server_url:
            result = self._send_jsonrpc("tools/call", {"name": tool_name, "arguments": arguments})
            # Standard MCP tool response format
            if isinstance(result, dict) and "content" in result:
                return result
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ],
                "isError": False,
            }

        handler = self._mock_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"MCP tool '{tool_name}' not found on server '{self.server_name}'")

        # Standard MCP execution return structure
        result_content = handler(arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result_content),
                }
            ],
            "isError": False,
        }
