"""
Unit tests for LiveKit Real-Time WebRTC Audio Adapter (Layer 1: Perception, Task 1.1).
"""

import pytest
from cognitive.perception.audio.livekit_adapter import (
    AudioChunk,
    AudioSession,
    LiveKitAdapter,
)


def test_establish_session_and_token():
    """Acceptance: Can establish WebRTC audio session and generate join token."""
    adapter = LiveKitAdapter(api_url="http://localhost:7880", api_key="test_key", api_secret="test_secret_12345678901234567890")
    session = adapter.establish_session(
        room_name="voice_conference_alpha",
        participant_identity="agent_user_42",
    )

    assert isinstance(session, AudioSession)
    assert session.room_name == "voice_conference_alpha"
    assert session.participant_identity == "agent_user_42"
    assert session.status == "connected"
    assert len(session.token) > 10
    assert session.is_active() is True


def test_stream_audio_chunks():
    """Acceptance: Can stream audio chunks and maintain sub-100ms latency."""
    adapter = LiveKitAdapter()
    session = adapter.establish_session("dev_room", "test_speaker")

    # Generate sample 16kHz PCM audio bytes (e.g. 640 bytes for 20ms of audio)
    raw_pcm = b"\x00\x01" * 320
    chunk = adapter.stream_audio_chunk(session, raw_pcm)

    assert isinstance(chunk, AudioChunk)
    assert chunk.byte_count == 640
    assert session.bytes_sent == 640
    assert session.chunks_sent == 1
    assert session.status == "streaming"
    # Verify sub-100ms bidirectional voice requirement
    assert session.latency_ms < 100.0

    # Stream a second chunk as an AudioChunk object
    second_chunk = AudioChunk(data=raw_pcm, duration_ms=20.0)
    adapter.stream_audio_chunk(session, second_chunk)
    assert session.chunks_sent == 2
    assert session.bytes_sent == 1280


def test_bidirectional_receive_and_disconnect():
    """Verify incoming chunk reception and session teardown."""
    adapter = LiveKitAdapter()
    session = adapter.establish_session("dev_room_2", "caller_1")

    # Simulate remote incoming audio
    in_chunk = AudioChunk(data=b"\x02\x03" * 160)
    adapter.receive_chunk(session, in_chunk)

    assert session.chunks_received == 1
    assert session.bytes_received == 320
    buffered = adapter.get_received_chunks(session)
    assert len(buffered) == 1

    # Disconnect
    adapter.disconnect(session)
    assert session.status == "closed"
    assert session.is_active() is False

    with pytest.raises(RuntimeError, match="inactive session"):
        adapter.stream_audio_chunk(session, b"overflow")

