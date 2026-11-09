"""Unit tests for Prefix Cache Optimizer (Task 9.5, Feature 9.14)."""

import pytest
from control.context.cache.prefix_optimizer import (
    PrefixCacheOptimizer,
    CacheableSection,
    SectionStability,
)


def test_prefix_reordering_acceptance():
    """Task 9.5 Acceptance: Static system prompt + tool definitions always appear first in context, maximizing cache hits."""
    # Arbitrary disorderly sections
    sections = [
        CacheableSection(
            name="recent_user_query",
            content="User: Tell me about project status.",
            stability=SectionStability.DYNAMIC_CONVERSATION,
            token_count=12,
        ),
        CacheableSection(
            name="active_tools",
            content="Tool: query_jira(id: str), query_github(repo: str)",
            stability=SectionStability.STATIC_TOOLS,
            token_count=25,
        ),
        CacheableSection(
            name="system_instructions",
            content="System: You are an enterprise AI brain assistant.",
            stability=SectionStability.STATIC_SYSTEM,
            token_count=18,
        ),
        CacheableSection(
            name="retrieved_docs",
            content="Doc: Project Phoenix sprint 12 metrics.",
            stability=SectionStability.SEMI_STATIC_KNOWLEDGE,
            token_count=40,
        ),
        CacheableSection(
            name="user_profile_memory",
            content="Memory: Alice, Principal Engineer.",
            stability=SectionStability.DYNAMIC_MEMORY,
            token_count=10,
        ),
    ]

    result = PrefixCacheOptimizer.assemble_optimized(sections)

    # 1. Verification of ordering: System -> Tools -> Knowledge -> Memory -> Conversation
    ordered_names = [s.name for s in result.ordered_sections]
    assert ordered_names == [
        "system_instructions",
        "active_tools",
        "retrieved_docs",
        "user_profile_memory",
        "recent_user_query",
    ]

    # 2. String starts with static system instructions followed by tool definitions
    assert result.optimized_prompt.startswith("System: You are an enterprise AI brain assistant.")
    assert result.optimized_prompt.find("Tool: query_jira") < result.optimized_prompt.find("User: Tell me")

    # 3. Cacheable ratio calculation
    assert result.static_prefix_tokens == 18 + 25
    assert result.dynamic_suffix_tokens == 40 + 10 + 12
    assert result.cacheable_ratio > 0.4


def test_prefix_overlap_measurement():
    """Feature 9.14: Verifies cache hit potential calculation between two sequential user turns."""
    static_prefix = (
        "System: You are an enterprise AI assistant with tool calling.\n\n"
        "Tool: search(query: str), run_calc(expr: str)"
    )

    prompt_turn_1 = f"{static_prefix}\n\nUser: Query 1"
    prompt_turn_2 = f"{static_prefix}\n\nUser: Query 2"

    ratio = PrefixCacheOptimizer.compute_prefix_overlap_ratio(prompt_turn_1, prompt_turn_2)
    # The common prefix is the vast majority of the prompt
    assert ratio > 0.85
