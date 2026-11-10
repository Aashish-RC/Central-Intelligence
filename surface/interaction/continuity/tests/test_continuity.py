"""Unit tests for ConversationContinuityEngine (Task 18.6)."""

import pytest
from surface.interaction.continuity.continuity_engine import (
    ConversationContinuityEngine,
)


@pytest.fixture
def engine():
    return ConversationContinuityEngine()


def test_conversation_started_on_web_continues_on_desktop(engine: ConversationContinuityEngine):
    """Acceptance test: Conversation started on web continues on desktop with full history."""
    session_id = "sess_continuity_001"
    web = "web"
    desktop = "desktop"

    # User starts on Web surface
    engine.post_turn(session_id, web, "msg_1", "user", "Design a zero-downtime deploy system")
    engine.post_turn(session_id, web, "msg_2", "assistant", "Use blue-green proxy swap with health probes.")

    # User began drafting follow-up on web
    engine.set_draft(session_id, web, "Can you provide a Kamal example?")

    # User switches to desktop app
    synced_history = engine.handoff_session(session_id, from_surface=web, to_surface=desktop)

    # Full history is present on desktop
    assert len(synced_history) == 2
    assert synced_history[0].content == "Design a zero-downtime deploy system"
    assert synced_history[1].content == "Use blue-green proxy swap with health probes."

    # Draft text is transferred
    draft = engine.get_surface_draft(session_id, desktop)
    assert draft == "Can you provide a Kamal example?"

    # User posts new reply from Desktop
    engine.post_turn(session_id, desktop, "msg_3", "user", "Can you provide a Kamal example?")
    engine.post_turn(session_id, desktop, "msg_4", "assistant", "Sure, here is the kamal deploy config...")

    # Back to web: syncing retrieves desktop messages
    web_history = engine.handoff_session(session_id, from_surface=desktop, to_surface=web)
    assert len(web_history) == 4
    assert [m.message_id for m in web_history] == ["msg_1", "msg_2", "msg_3", "msg_4"]

