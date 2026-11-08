"""Tests for RulesBinder."""

import pytest
from agent_builder.binding.rules_binder import RulesBinder


@pytest.fixture
def binder():
    return RulesBinder()


def test_bind_rules_default_modes(binder):
    # Read-only task gets auto_review
    read_only_text = "Summarize research documents and explain key findings"
    binding = binder.bind_rules(read_only_text)
    assert binding.permission_mode == "auto_review"
    assert "rule_deny_secret_leakage" in binding.active_rules

    # Action mutating task gets ask_on_changes
    mutating_text = "Refactor code files, modify modules, and delete obsolete test files"
    mutating_binding = binder.bind_rules(mutating_text)
    assert mutating_binding.permission_mode == "ask_on_changes"
    assert "rule_sandbox_ephemeral_cleanup" in mutating_binding.active_rules


def test_bind_rules_explicit_request(binder):
    text = "Read simple text"
    binding = binder.bind_rules(text, requested_mode="always_ask")
    assert binding.permission_mode == "always_ask"
