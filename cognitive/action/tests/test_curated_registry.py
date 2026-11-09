"""Unit tests for Curated Tool Registry (5.08)."""

import pytest
from cognitive.action.registry.curated_registry import (
    CuratedToolMetadata,
    CuratedToolRegistry,
    ToolAccessDeniedError,
    ToolRateLimitExceededError,
    ToolValidationError,
)


def test_tool_registration_and_approval():
    registry = CuratedToolRegistry()
    tool = CuratedToolMetadata(
        tool_id="mcp:filesystem:write",
        name="Filesystem Writer",
        category="storage",
        is_approved=False,
        required_roles=["dev_agent"],
        rate_limit_per_minute=5,
    )
    registry.register_tool(tool)

    # Initially unapproved
    with pytest.raises(ToolAccessDeniedError, match="has not been approved"):
        registry.check_access("mcp:filesystem:write", "agent_1", ["dev_agent"])

    # Admin approves
    registry.approve_tool("mcp:filesystem:write", "admin_alice")
    assert registry.get_tool("mcp:filesystem:write").is_approved is True

    # Accessible by dev_agent
    registry.check_access("mcp:filesystem:write", "agent_1", ["dev_agent"])

    # Revoke tool
    registry.revoke_tool("mcp:filesystem:write", "Security concern")
    with pytest.raises(ToolAccessDeniedError, match="has not been approved"):
        registry.check_access("mcp:filesystem:write", "agent_1", ["dev_agent"])


def test_role_based_access_control():
    registry = CuratedToolRegistry()
    tool = CuratedToolMetadata(
        tool_id="nango:github:deploy",
        name="GitHub Deploy",
        is_approved=True,
        required_roles=["deployer"],
    )
    registry.register_tool(tool)

    # Agent with wrong role denied
    with pytest.raises(ToolAccessDeniedError, match="lacks required roles"):
        registry.check_access("nango:github:deploy", "agent_guest", ["viewer"])

    # Agent with admin role bypasses specific role requirement
    registry.check_access("nango:github:deploy", "agent_super", ["admin"])

    # Agent with correct role allowed
    registry.check_access("nango:github:deploy", "agent_devops", ["deployer"])


def test_rate_limiting():
    registry = CuratedToolRegistry()
    tool = CuratedToolMetadata(
        tool_id="http:webhook:send",
        name="Send Webhook",
        is_approved=True,
        rate_limit_per_minute=2,
    )
    registry.register_tool(tool)

    # 1st invocation
    registry.check_and_record_rate_limit("http:webhook:send", "agent_1")
    # 2nd invocation
    registry.check_and_record_rate_limit("http:webhook:send", "agent_1")

    # 3rd invocation exceeds rate limit of 2 rpm
    with pytest.raises(ToolRateLimitExceededError, match="Rate limit exceeded"):
        registry.check_and_record_rate_limit("http:webhook:send", "agent_1")


def test_parameter_schema_validation():
    registry = CuratedToolRegistry()
    tool = CuratedToolMetadata(
        tool_id="sql:query:execute",
        name="SQL Executor",
        is_approved=True,
        input_schema={
            "required": ["query", "limit"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "dry_run": {"type": "boolean"},
            },
        },
    )
    registry.register_tool(tool)

    # Valid params
    registry.validate_parameters("sql:query:execute", {"query": "SELECT 1", "limit": 10, "dry_run": True})

    # Missing required parameter
    with pytest.raises(ToolValidationError, match="Missing required parameter 'limit'"):
        registry.validate_parameters("sql:query:execute", {"query": "SELECT 1"})

    # Invalid type
    with pytest.raises(ToolValidationError, match="must be an integer"):
        registry.validate_parameters("sql:query:execute", {"query": "SELECT 1", "limit": "ten"})
