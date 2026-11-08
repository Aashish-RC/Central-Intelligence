"""Unit tests for ToolRegistry: tool registration, discovery, and schema generation."""

import pytest
from tools_mcp.catalog.registry import ToolRegistry
from tools_mcp.core.models import ToolDefinition, ToolParameter, ToolType


@pytest.fixture
def registry():
    return ToolRegistry(include_builtins=True)


def test_builtin_tools_loaded(registry):
    tools = registry.list_tools()
    tool_names = [t.name for t in tools]

    assert "calculator" in tool_names
    assert "string_transform" in tool_names
    assert "json_query" in tool_names
    assert "hash_generator" in tool_names
    assert "current_timestamp" in tool_names


def test_custom_tool_registration(registry):
    custom_tool = ToolDefinition(
        name="weather_lookup",
        description="Fetch weather forecast for a given city",
        tool_type=ToolType.CUSTOM,
        parameters=[
            ToolParameter(name="city", type="string", description="City name", required=True),
            ToolParameter(name="units", type="string", description="metric or imperial", required=False, default="metric"),
        ],
    )
    registry.register_tool(custom_tool)

    fetched = registry.get_tool("weather_lookup")
    assert fetched is not None
    assert fetched.name == "weather_lookup"
    assert len(fetched.parameters) == 2


def test_json_schema_generation(registry):
    schemas = registry.get_tools_schema()
    calc_schema = next(s for s in schemas if s["function"]["name"] == "calculator")

    assert calc_schema["type"] == "function"
    assert calc_schema["function"]["name"] == "calculator"
    assert "expression" in calc_schema["function"]["parameters"]["properties"]
    assert "expression" in calc_schema["function"]["parameters"]["required"]
