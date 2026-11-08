"""Tests for Barge-in Interruption."""

import pytest
from voice_speech.core.models import VoiceSessionState
from voice_speech.duplex.voice_session_runner import VoiceSessionRunner


def test_barge_in_interruption_during_speaking():
    runner = VoiceSessionRunner()
    runner.start_session()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    speech_data = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:Explain quantum encryption"
    turn = runner.process_spoken_turn(speech_data)
    assert runner.get_session_state() == VoiceSessionState.SPEAKING
    assert turn.transcript == "Explain quantum encryption"

    # User starts speaking to interrupt the agent
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.LISTENING


def test_barge_in_when_idle_is_safe():
    runner = VoiceSessionRunner()
    assert runner.get_session_state() == VoiceSessionState.IDLE
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.IDLE


def test_duplex_barge_in_state_transition_sequence():
    """Verify full state machine sequence: IDLE -> LISTENING -> PROCESSING -> SPEAKING -> INTERRUPTED -> LISTENING."""
    runner = VoiceSessionRunner()
    assert runner.state_history == [VoiceSessionState.IDLE]

    runner.start_session()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    speech_data = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:Status report"
    runner.process_spoken_turn(speech_data)
    assert runner.get_session_state() == VoiceSessionState.SPEAKING

    # Trigger barge in while speaking
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    # Verify complete chronological transition trail
    assert runner.state_history == [
        VoiceSessionState.IDLE,
        VoiceSessionState.LISTENING,
        VoiceSessionState.PROCESSING,
        VoiceSessionState.SPEAKING,
        VoiceSessionState.INTERRUPTED,
        VoiceSessionState.LISTENING,
    ]


def test_interrupted_turn_allows_immediate_subsequent_turn():
    """Verify an interrupted turn smoothly accepts the interrupting utterance."""
    runner = VoiceSessionRunner()
    runner.start_session()

    # Turn 1: agent starts speaking
    turn1_audio = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:First long monologue"
    runner.process_spoken_turn(turn1_audio)
    assert runner.get_session_state() == VoiceSessionState.SPEAKING

    # User interrupts
    runner.trigger_barge_in()
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    # Turn 2: user speaks immediate interruption command
    turn2_audio = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:Stop and cancel"
    turn2 = runner.process_spoken_turn(turn2_audio)
    assert turn2.transcript == "Stop and cancel"
    assert runner.get_session_state() == VoiceSessionState.SPEAKING

    # End session gracefully
    runner.end_session()
    assert runner.get_session_state() == VoiceSessionState.IDLE


def test_livekit_microphone_audio_automatically_silences_bot_tts():
    """Done when: Incoming microphone audio automatically silences ongoing bot TTS playback."""
    runner = VoiceSessionRunner()
    connected = runner.connect_livekit_room(
        url="wss://livekit.internal:7880",
        token="jwt-token-12345",
        room_name="voice-call-alpha"
    )
    assert connected is True
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    # Bot speaks response to a question
    prompt_audio = b"\x01\x02" * 8000 + b"PHEONIX_SPEECH:Give me a 10 minute lecture"
    runner.process_spoken_turn(prompt_audio)
    assert runner.is_bot_speaking() is True
    assert runner.active_playback_silenced is False

    # Incoming microphone audio packet from user (VAD detects speech)
    mic_audio_frame = b"\x03\x04" * 160  # 10ms audio chunk
    interrupted = runner.on_incoming_microphone_audio(mic_audio_frame, vad_detected=True)

    # Verify ongoing bot TTS was automatically silenced
    assert interrupted is True
    assert runner.active_playback_silenced is True
    assert runner.is_bot_speaking() is False
    assert runner.get_session_state() == VoiceSessionState.LISTENING

    # Silence when not speaking returns False (idempotent)
    assert runner.on_incoming_microphone_audio(mic_audio_frame, vad_detected=True) is False
