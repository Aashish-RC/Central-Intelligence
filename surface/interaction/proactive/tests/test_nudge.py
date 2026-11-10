"""Unit tests for ProactiveNudgeEngine (Task 18.8)."""

import pytest
from surface.interaction.proactive.nudge_engine import (
    ProactiveNudgeEngine,
    NudgePriority,
)


@pytest.fixture
def nudge_engine():
    return ProactiveNudgeEngine()


def test_urgent_nudge_dispatched_immediately(nudge_engine: ProactiveNudgeEngine):
    """Acceptance test: Urgent nudge dispatched immediately across surfaces."""
    delivered = []

    def on_nudge(nudge):
        delivered.append(nudge)

    nudge_engine.add_listener(on_nudge)

    urgent = nudge_engine.dispatch_urgent_nudge(
        title="Security Alert: Anomalous API Key Usage",
        message="Unusual egress spike detected on key 'prod_key_alpha'",
    )

    assert urgent.dispatched is True
    assert urgent.priority == NudgePriority.URGENT
    assert len(delivered) == 1
    assert delivered[0].title == "Security Alert: Anomalous API Key Usage"
    assert "desktop" in delivered[0].target_surfaces


def test_daily_brief_at_9_am(nudge_engine: ProactiveNudgeEngine):
    """Acceptance test: Daily brief at 9 AM is scheduled and delivered when time arrives."""
    delivered = []
    nudge_engine.add_listener(lambda n: delivered.append(n))

    # 9:00 AM timestamp
    t_9am = 1770000000.0
    brief = nudge_engine.schedule_daily_brief(
        title="Morning Intelligence Digest",
        message="3 priority tickets pending review; system health 100%.",
        scheduled_timestamp=t_9am,
    )
    assert brief.dispatched is False

    # Check at 8:55 AM (5 minutes before) -> Not due yet
    t_855am = t_9am - 300.0
    due_early = nudge_engine.poll_due_nudges(current_time=t_855am)
    assert len(due_early) == 0
    assert brief.dispatched is False
    assert len(delivered) == 0

    # Check at 9:00 AM -> Due and dispatched
    due_on_time = nudge_engine.poll_due_nudges(current_time=t_9am)
    assert len(due_on_time) == 1
    assert due_on_time[0].title == "Morning Intelligence Digest"
    assert due_on_time[0].dispatched is True
    assert len(delivered) == 1

