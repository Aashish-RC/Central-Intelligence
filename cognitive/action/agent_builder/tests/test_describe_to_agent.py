"""Tests for DescribeToAgentCompiler."""

import pytest
from agent_builder.core.models import DescribeAgentRequest
from agent_builder.compiler.describe_to_agent import DescribeToAgentCompiler


@pytest.fixture
def compiler():
    return DescribeToAgentCompiler()


def test_compile_agent_invalid_prompt(compiler):
    req = DescribeAgentRequest(prompt="hi")
    result = compiler.compile_agent(req)
    assert result.success is False
    assert len(result.validation_errors) > 0


def test_compile_agent_security_auditor(compiler):
    prompt = "Create an automated security code auditor that scans Python repositories for secret leaks and injection vulnerabilities"
    req = DescribeAgentRequest(
        prompt=prompt,
        target_domain="security",
        requested_permission_mode="ask_on_changes",
    )
    result = compiler.compile_agent(req)

    assert result.success is True
    spec = result.specification
    assert spec is not None
    assert "Security" in spec.name
    assert "OWASP Top 10" in spec.persona.expertise_areas or "Secret Detection" in spec.persona.expertise_areas
    assert spec.rules_binding.permission_mode == "ask_on_changes"
    assert "code_interpreter" in spec.tool_binding.tool_ids or "grep_search" in spec.tool_binding.tool_ids
    assert result.compile_duration_ms >= 0.0
