"""End-to-End Tests for Voice and Speech: Verifies that you can hold a spoken conversation."""

import pytest
from voice_speech.core.models import VoiceSessionState
from voice_speech.duplex.voice_session_runner import VoiceSessionRunner


def test_hold_spoken_conversation():
    """Core Done When Criteria: You can hold a spoken conversation."""
    runner = VoiceSessionRunner()

    # Step 1: User initiates real-time voice session
    runner.start_session()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    # Step 2: First conversational turn: User asks a question in speech
    user_audio_turn_1 = b"\x01\x02" * 16000 + b"PHEONIX_SPEECH:What is the current server load?"
    turn_1 = runner.process_spoken_turn(user_audio_turn_1)

    assert turn_1.transcript == "What is the current server load?"
    assert "Understood" in turn_1.agent_response_text
    assert len(turn_1.response_audio_bytes) > 44  # Valid WAV waveform
    assert turn_1.roundtrip_latency_ms > 0.0
    assert runner.get_session_state() == VoiceSessionState.SPEAKING

    # Step 3: Second conversational turn: User follows up with another spoken query
    user_audio_turn_2 = b"\x01\x02" * 16000 + b"PHEONIX_SPEECH:Please scale down idle containers"
    turn_2 = runner.process_spoken_turn(user_audio_turn_2)

    assert turn_2.transcript == "Please scale down idle containers"
    assert "scale down idle containers" in turn_2.agent_response_text
    assert len(turn_2.response_audio_bytes) > 44
    assert len(runner.turns) == 2

    # Step 4: End session
    runner.end_session()
    assert runner.get_session_state() == VoiceSessionState.IDLE
