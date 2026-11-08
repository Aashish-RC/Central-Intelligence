"""Tests for ToolMatcher."""

import pytest
from agent_builder.compiler.tool_matcher import ToolMatcher


@pytest.fixture
def matcher():
    return ToolMatcher()


def test_match_tools_coding_prompt(matcher):
    prompt = "Create a bot that can execute python scripts, find function definitions, and debug code"
    binding = matcher.match_tools(prompt)

    assert "code_interpreter" in binding.tool_ids
    assert "grep_search" in binding.tool_ids
    assert "code_interpreter" in binding.consequential_tools


def test_match_tools_web_research_prompt(matcher):
    prompt = "Search online research articles, browse news sites, and crawl documentation"
    binding = matcher.match_tools(prompt)

    assert "web_search" in binding.tool_ids
    assert "browser_automation" in binding.tool_ids
    assert "mcp-browser-server" in binding.mcp_server_ids


def test_match_tools_generic_fallback(matcher):
    prompt = "Help me think about general ideas and brainstorm"
    binding = matcher.match_tools(prompt)

    # Fallback default tools provided
    assert "file_reader" in binding.tool_ids
    assert "grep_search" in binding.tool_ids
