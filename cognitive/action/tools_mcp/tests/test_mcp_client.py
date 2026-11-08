"""Unit tests for Model Context Protocol (MCP) Client."""

import pytest
from tools_mcp.core.models import ToolParameter, ToolType
from tools_mcp.mcp.client import MCPClient


@pytest.fixture
def mcp():
    client = MCPClient(server_name="test_sqlite_mcp")
    client.register_mcp_server_mock(
        name="read_query",
        description="Execute a SELECT query against the SQLite database",
        parameters=[ToolParameter(name="query", type="string", required=True)],
        handler=lambda args: [{"id": 1, "name": "Pheonix Item"}],
    )
    return client


def test_mcp_tool_discovery(mcp):
    tools = mcp.list_mcp_tools()
    assert len(tools) == 1
    assert tools[0].name == "read_query"
    assert tools[0].tool_type == ToolType.MCP


def test_mcp_tool_call(mcp):
    result = mcp.call_mcp_tool("read_query", {"query": "SELECT * FROM items;"})
    assert "content" in result
    assert result["isError"] is False
    assert "Pheonix Item" in result["content"][0]["text"]


def test_mcp_tool_not_found(mcp):
    with pytest.raises(ValueError, match="not found on server"):
        mcp.call_mcp_tool("nonexistent_tool", {})
