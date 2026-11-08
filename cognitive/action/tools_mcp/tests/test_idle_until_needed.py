"""Unit tests verifying idle-until-needed rule: A connector asks for credentials only when used."""

import pytest
from tools_mcp.auth.on_demand_auth import OnDemandAuthBridge
from tools_mcp.catalog.registry import ToolRegistry
from tools_mcp.core.models import (
    CredentialStatus,
    ToolDefinition,
    ToolInvocation,
    ToolParameter,
    ToolType,
)
from tools_mcp.runner.dispatcher import ToolDispatcher


@pytest.fixture
def setup():
    registry = ToolRegistry(include_builtins=False)
    auth_bridge = OnDemandAuthBridge()
    dispatcher = ToolDispatcher(registry=registry, auth_bridge=auth_bridge)
    return registry, auth_bridge, dispatcher


def test_connector_asks_for_credentials_only_when_used(setup):
    """Core verification: A connector asks for credentials strictly when invoked."""
    registry, auth_bridge, dispatcher = setup

    # Register an unauthenticated external connector (e.g. GitHub Issue Creator)
    github_tool = ToolDefinition(
        name="github_create_issue",
        description="Creates an issue in a GitHub repository",
        tool_type=ToolType.CONNECTOR,
        requires_auth=True,
        credential_name="GITHUB_TOKEN",
        parameters=[
            ToolParameter(name="repo", type="string", required=True),
            ToolParameter(name="title", type="string", required=True),
        ],
    )
    registry.register_tool(github_tool)

    # Register execution mock
    dispatcher.register_custom_handler(
        "github_create_issue",
        lambda args: f"Issue created: '{args['title']}' in '{args['repo']}' using {auth_bridge.get_credential('GITHUB_TOKEN')[:4]}***",
    )

    # 1. Before invocation: tool must be idle and NO credentials requested
    assert github_tool.is_idle is True
    assert github_tool.call_count == 0
    assert len(auth_bridge.get_pending_requests()) == 0

    # 2. Invoke tool without credentials
    invocation = ToolInvocation(
        tool_name="github_create_issue",
        arguments={"repo": "pheonix/core", "title": "Implement MCP"},
    )
    res1 = dispatcher.dispatch(invocation)

    # The tool MUST pause, ask for credentials, and enqueue the request
    assert res1.success is False
    assert res1.auth_required is True
    assert "GITHUB_TOKEN" in res1.error

    # Auth queue now contains the pending credential request
    pending = auth_bridge.get_pending_requests()
    assert len(pending) == 1
    assert pending[0].tool_name == "github_create_issue"
    assert pending[0].credential_name == "GITHUB_TOKEN"
    assert pending[0].status == CredentialStatus.REQUESTED

    # 3. Supply the credential
    auth_bridge.provide_credential("GITHUB_TOKEN", "ghp_secureToken12345")
    assert len(auth_bridge.get_pending_requests()) == 0
    assert auth_bridge.has_credential("GITHUB_TOKEN") is True

    # 4. Re-invoke tool with credentials present
    res2 = dispatcher.dispatch(invocation)
    assert res2.success is True
    assert "Issue created: 'Implement MCP' in 'pheonix/core' using ghp_***" in res2.output

    # Tool is now active (no longer idle)
    updated_tool = registry.get_tool("github_create_issue")
    assert updated_tool.is_idle is False
    assert updated_tool.call_count >= 1
