"""Unit tests for Agenta Team Workspace Adapter (Task 7.3)."""

import pytest
from cognitive.learning.agenta.agenta_adapter import (
    AgentaAdapter,
    AgentaWorkspace,
    AgentaApp,
)


def test_can_create_an_agent_in_agenta_workspace():
    adapter = AgentaAdapter()

    # Create workspace
    workspace = adapter.create_workspace(
        name="Cognitive Core Team",
        owner_id="team_lead",
        description="Collaboration workspace for Layer 7 agents",
    )
    assert workspace.workspace_id.startswith("ws_")
    assert workspace.name == "Cognitive Core Team"
    assert "team_lead" in workspace.members

    # Create agent application
    agent = adapter.create_agent(
        workspace_id=workspace.workspace_id,
        name="Research Analyst Agent",
        app_type="reasoning_workflow",
        description="Extracts synthesis from multi-source document repositories",
        default_prompt="You are a professional research analyst.",
    )

    assert agent.app_id.startswith("app_")
    assert agent.app_name == "Research Analyst Agent"
    assert agent.workspace_id == workspace.workspace_id
    assert "default" in agent.variants

    # List agents
    agent_list = adapter.list_agents(workspace.workspace_id)
    assert len(agent_list) == 1
    assert agent_list[0].app_id == agent.app_id


def test_agent_variant_and_deployment():
    adapter = AgentaAdapter()
    ws = adapter.create_workspace(name="QA Testing")
    agent = adapter.create_agent(workspace_id=ws.workspace_id, name="Evaluator")

    # Add variant
    variant = adapter.add_variant(
        app_id=agent.app_id,
        variant_name="candidate_v2",
        parameters={"temperature": 0.2, "top_p": 0.95},
        system_prompt="Strict evaluation mode enabled.",
    )
    assert variant.variant_name == "candidate_v2"
    assert variant.is_deployed is False

    # Deploy variant
    deployed = adapter.deploy_variant(
        app_id=agent.app_id,
        variant_name="candidate_v2",
        environment="production",
    )
    assert deployed is True
    assert agent.variants["candidate_v2"].is_deployed is True
    assert agent.variants["candidate_v2"].environment == "production"
