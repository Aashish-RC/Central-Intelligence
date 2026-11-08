"""End-to-End Tests for Agent Builder: Verifies that a plain-language request produces a working agent."""

import pytest
from agent_builder.core.models import DescribeAgentRequest
from agent_builder.compiler.describe_to_agent import DescribeToAgentCompiler
from agent_builder.runtime.agent_instantiator import AgentInstantiator


def test_plain_language_request_produces_working_agent():
    """Core Done When Criteria: A plain-language request produces a working agent."""
    compiler = DescribeToAgentCompiler()
    instantiator = AgentInstantiator()

    # Step 1: User provides a plain-language prompt describing target agent
    plain_language_prompt = (
        "Build an expert Python refactoring agent that analyzes codebase structure, "
        "finds dead functions using grep, executes test suites, and proposes clean modular refactorings."
    )
    request = DescribeAgentRequest(
        prompt=plain_language_prompt,
        target_domain="software_engineering",
    )

    # Step 2: Compile the request into a formal AgentSpecification
    build_result = compiler.compile_agent(request)
    assert build_result.success is True
    spec = build_result.specification
    assert spec is not None
    assert spec.name == "Python Code Refactorer"
    assert "code_interpreter" in spec.tool_binding.tool_ids
    assert "grep_search" in spec.tool_binding.tool_ids
    assert len(spec.rules_binding.active_rules) >= 3

    # Step 3: Instantiating and executing the generated agent proves it is a WORKING agent
    test_task = "Analyze d:/pheonix/core and refactor unused legacy helpers"
    exec_result = instantiator.execute_agent(spec, test_task)

    assert exec_result.status == "completed"
    assert exec_result.agent_id == spec.agent_id
    assert "Python Code Refactorer" in exec_result.response_text
    assert len(exec_result.tools_invoked) > 0
    assert exec_result.duration_ms >= 0.0
