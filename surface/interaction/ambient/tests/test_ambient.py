"""Unit tests for AmbientModeManager (Task 18.9)."""

import pytest
from surface.interaction.ambient.ambient_mode import (
    AmbientModeManager,
    AmbientState,
)


@pytest.fixture
def ambient():
    return AmbientModeManager(wake_words=["hey central", "central"])


def test_wake_word_activates_listening_and_presence_indicator(ambient: AmbientModeManager):
    """Acceptance test: Wake word -> AI starts listening; presence indicator active."""
    presence_updates = []
    ambient.add_presence_listener(lambda state, presence: presence_updates.append((state, presence)))

    # Initially dormant
    assert ambient.state == AmbientState.IDLE_DISABLED
    assert ambient.presence.is_active is False

    # 1. Opt-in arms wake-word detection
    armed = ambient.opt_in_and_arm(user_consent=True)
    assert armed is True
    assert ambient.state == AmbientState.ARMED_LISTENING_WAKE_WORD
    assert ambient.presence.is_active is True
    assert ambient.presence.color == "amber_armed"
    assert ambient.presence.is_recording_audio is False

    # 2. General background conversation without wake word
    activated_noise = ambient.process_audio_frame("Can you pass the salt please?")
    assert activated_noise is False
    assert ambient.state == AmbientState.ARMED_LISTENING_WAKE_WORD
    assert ambient.presence.is_recording_audio is False

    # 3. Wake word spoken -> AI activates and presence indicator turns active green
    activated_wake = ambient.process_audio_frame("Hey Central, summarize today's calendar")
    assert activated_wake is True
    assert ambient.state == AmbientState.ACTIVE_LISTENING
    assert ambient.presence.is_active is True
    assert ambient.presence.color == "green_active"
    assert ambient.presence.is_recording_audio is True
    assert ambient.presence.badge_text == "Active Listening"

    # 4. Turn complete -> returns to armed wake-word listening
    ambient.finish_utterance()
    assert ambient.state == AmbientState.ARMED_LISTENING_WAKE_WORD
    assert ambient.presence.is_recording_audio is False

    # 5. Disarm completely
    ambient.disarm()
    assert ambient.state == AmbientState.IDLE_DISABLED
    assert ambient.presence.is_active is False
