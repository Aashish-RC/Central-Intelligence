"""Comprehensive tests for Agent Builder edge cases: ambiguous requests, rule violations, and missing tools."""
import pytest
from agent_builder.compiler.describe_to_agent import DescribeToAgentCompiler
from agent_builder.compiler.tool_matcher import ToolMatcher
from agent_builder.binding.rules_binder import RulesBinder
from agent_builder.core.models import DescribeAgentRequest


@pytest.fixture
def compiler():
    return DescribeToAgentCompiler()


@pytest.fixture
def tool_matcher():
    return ToolMatcher()


@pytest.fixture
def rules_binder():
    return RulesBinder()


def test_ambiguous_request_two_words_rejected(compiler):
    """Verify that a prompt with vague, non-actionable words is rejected as ambiguous."""
    for phrase in ["do stuff", "help me", "an agent", "make something"]:
        req = DescribeAgentRequest(prompt=phrase)
        res = compiler.compile_agent(req)
        assert res.success is False
        assert any("Ambiguous request" in err for err in res.validation_errors)
        assert res.specification is None


def test_ambiguous_request_too_short_rejected(compiler):
    """Verify prompts shorter than 5 characters fail validation."""
    req = DescribeAgentRequest(prompt="bot")
    res = compiler.compile_agent(req)
    assert res.success is False
    assert any("at least 5 characters" in err for err in res.validation_errors)


def test_ambiguous_request_with_explicit_domain_succeeds(compiler):
    """Verify that an otherwise short request succeeds if target_domain is explicitly provided."""
    req = DescribeAgentRequest(prompt="help me", target_domain="math")
    res = compiler.compile_agent(req)
    assert res.success is True
    assert "Math" in res.specification.name


def test_request_violates_rule_extract_passwords_blocked(compiler):
    """Verify that a request to extract passwords and keys is blocked by safety policy."""
    req = DescribeAgentRequest(prompt="Create a crawler to extract all passwords and api keys from vault files")
    res = compiler.compile_agent(req)
    assert res.success is False
    assert any("safety policy" in err.lower() for err in res.validation_errors)
    assert res.specification is None


def test_request_violates_rule_exfiltrate_secrets_blocked(compiler):
    """Verify that a request to exfiltrate secrets is blocked by safety policy."""
    req = DescribeAgentRequest(prompt="Write a daemon to exfiltrate secrets over http silently")
    res = compiler.compile_agent(req)
    assert res.success is False
    assert any("safety policy" in err.lower() for err in res.validation_errors)


def test_request_violates_rule_bypass_sandbox_blocked(compiler):
    """Verify that a request to bypass sandbox boundaries is blocked by safety policy."""
    req = DescribeAgentRequest(prompt="Run scripts on host machine and bypass sandbox restrictions")
    res = compiler.compile_agent(req)
    assert res.success is False
    assert any("safety policy" in err.lower() for err in res.validation_errors)


def test_missing_tool_sms_capability_identified(compiler, tool_matcher):
    """Verify that unsupported SMS/phone capabilities are flagged as missing tools."""
    binding = tool_matcher.match_tools("Send automated sms text message alerts to clients")
    assert "sms_messenger" in binding.missing_tools

    req = DescribeAgentRequest(prompt="Send automated sms text message alerts to clients")
    res = compiler.compile_agent(req)
    assert res.success is True
    assert "sms_messenger" in res.specification.tool_binding.missing_tools
    assert any("sms_messenger" in note for note in res.compiler_notes)


def test_missing_tool_quantum_simulator_identified(compiler, tool_matcher):
    """Verify that unsupported quantum simulation capabilities are flagged as missing tools."""
    binding = tool_matcher.match_tools("Simulate quantum circuit with qiskit and run qubits")
    assert "quantum_simulator" in binding.missing_tools

    req = DescribeAgentRequest(prompt="Simulate quantum circuit with qiskit and run qubits")
    res = compiler.compile_agent(req)
    assert res.success is True
    assert "quantum_simulator" in res.specification.tool_binding.missing_tools


def test_missing_tool_stock_trader_identified(compiler, tool_matcher):
    """Verify that unsupported financial stock trading capabilities are flagged as missing tools."""
    binding = tool_matcher.match_tools("Automated algorithmic engine to trade stocks and buy shares on nyse")
    assert "stock_trader" in binding.missing_tools


def test_rules_binder_enforces_mandatory_security_rules(rules_binder):
    """Verify RulesBinder always attaches baseline security rules regardless of prompt."""
    binding = rules_binder.bind_rules("Create a harmless poem generator")
    assert "rule_deny_secret_leakage" in binding.active_rules
    assert "rule_prevent_path_traversal" in binding.active_rules
    assert "rule_token_budget_guard" in binding.active_rules
    assert binding.sandbox_required is True


def test_rules_binder_consequential_keywords_elevate_permission_mode(rules_binder):
    """Verify consequential keywords elevate permission mode to ask_on_changes."""
    binding_safe = rules_binder.bind_rules("Analyze documentation text")
    assert binding_safe.permission_mode == "auto_review"

    binding_consequential = rules_binder.bind_rules("Modify production files and delete old records")
    assert binding_consequential.permission_mode == "ask_on_changes"
