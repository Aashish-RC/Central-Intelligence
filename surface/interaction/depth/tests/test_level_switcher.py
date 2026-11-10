"""Unit tests for DepthLevelSwitcher (Task 18.7)."""

import pytest
from surface.interaction.depth.level_switcher import (
    DepthLevelSwitcher,
    DepthLevel,
)


@pytest.fixture
def switcher():
    return DepthLevelSwitcher(initial_level=DepthLevel.GUIDED)


def test_switch_from_guided_to_pro_and_inspect_transparency_panel(switcher: DepthLevelSwitcher):
    """Acceptance test: User can switch from Guided to Pro; transparency panel shows sources."""
    assert switcher.current_level == DepthLevel.GUIDED
    assert switcher.get_transparency_panel().reasoning_traces_visible is False

    # Switch to Pro mode
    level = switcher.set_depth_level(DepthLevel.PRO)
    assert level == DepthLevel.PRO
    assert switcher.get_transparency_panel().reasoning_traces_visible is True
    assert "expert-level" in switcher.get_system_prompt_modifier()

    # Model picker always available
    selected = switcher.select_model("claude-3-7-sonnet")
    assert selected == "claude-3-7-sonnet"

    # Simulate turn execution recording sources & memories
    sources = [
        {"title": "Postgres RLS Documentation", "url": "https://www.postgresql.org/docs/current/ddl-rowsecurity.html"},
        {"file": "platform/data/supabase/supabase_adapter.py", "lines": "10-45"},
    ]
    memories = [
        {"memory_id": "mem_pref_001", "content": "User prefers async Python idioms."},
    ]

    panel = switcher.record_turn_provenance(
        sources=sources,
        memories=memories,
        prompt_tokens=450,
        completion_tokens=220,
        cost_usd=0.0042,
        latency_ms=310.0,
    )

    # Transparency panel displays sources, memories, cost
    assert len(panel.sources_used) == 2
    assert panel.sources_used[0]["title"] == "Postgres RLS Documentation"
    assert len(panel.memories_recalled) == 1
    assert panel.memories_recalled[0]["memory_id"] == "mem_pref_001"
    assert panel.estimated_cost_usd == 0.0042
    assert panel.latency_ms == 310.0

