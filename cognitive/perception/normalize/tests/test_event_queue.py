"""
Unit tests for Unified Input Normalizer and Event Queue (Layer 1: Perception, Task 1.8).
"""

import time
import pytest
from cognitive.perception.audio.livekit_adapter import AudioChunk
from cognitive.perception.normalize.event_queue import InputNormalizer
from cognitive.perception.normalize.provenance import (
    InputModality,
    NormalizedEvent,
    TrustLevel,
)
from cognitive.perception.screen.screenpipe_adapter import OCRFrame


@pytest.mark.asyncio
async def test_unified_multi_modal_ingestion_and_provenance():
    """
    Acceptance: Audio from LiveKit + text from user + OCR from screenpipe
    are all in the same event queue with correct timestamps and provenance.
    """
    normalizer = InputNormalizer()
    t0 = 1700000000.0

    # 1. LiveKit audio chunk
    livekit_audio = AudioChunk(data=b"\x00\x01" * 160, duration_ms=20.0, timestamp=t0)
    ev_audio = await normalizer.ingest(
        raw_input=livekit_audio,
        source="livekit",
        modality=InputModality.AUDIO,
        timestamp=t0,
        metadata={"codec": "pcm_16khz", "room": "dev_room"},
    )
    assert ev_audio.source == "livekit"
    assert ev_audio.modality == "audio"
    assert ev_audio.trust == TrustLevel.MEDIUM.value
    assert ev_audio.timestamp == t0

    # 2. Typed text from user
    ev_user = await normalizer.ingest(
        raw_input="Can you analyze the open pull request on my screen?",
        source="user",
        modality=InputModality.TEXT,
        timestamp=t0 + 1.5,
    )
    assert ev_user.source == "user"
    assert ev_user.modality == "text"
    assert ev_user.trust == TrustLevel.HIGH.value
    assert ev_user.timestamp == t0 + 1.5

    # 3. Screen OCR frame from Screenpipe
    screen_frame = OCRFrame(
        app_name="Google Chrome",
        window_title="PR #104: Fix authentication race condition",
        text="Reviewing files changed: 3 commits, 4 files modified.",
        timestamp=t0 + 2.0,
    )
    ev_ocr = await normalizer.ingest(
        raw_input=screen_frame,
        source="screenpipe",
        modality=InputModality.SCREEN_OCR,
        timestamp=t0 + 2.0,
        metadata={"window_title": screen_frame.window_title},
    )
    assert ev_ocr.source == "screenpipe"
    assert ev_ocr.modality == "screen_ocr"
    assert ev_ocr.timestamp == t0 + 2.0

    # Verify queue depth
    assert normalizer.size() == 3

    # Consume all events sequentially and verify correct ordering
    consumed_1 = await normalizer.consume()
    consumed_2 = await normalizer.consume()
    consumed_3 = await normalizer.consume()

    assert consumed_1.source == "livekit"
    assert isinstance(consumed_1.content, AudioChunk)
    assert consumed_1.provenance.metadata["codec"] == "pcm_16khz"

    assert consumed_2.source == "user"
    assert "analyze the open pull request" in consumed_2.content

    assert consumed_3.source == "screenpipe"
    assert isinstance(consumed_3.content, OCRFrame)
    assert "PR #104" in consumed_3.content.window_title

    assert normalizer.size() == 0


def test_custom_source_trust_overrides():
    """Verify custom trust levels can be configured per ingestion source."""
    normalizer = InputNormalizer()
    normalizer.set_source_trust("untrusted_webhook", TrustLevel.UNTRUSTED)

    ev = normalizer.ingest_sync(
        raw_input={"payload": "anonymous"},
        source="untrusted_webhook",
        modality="document",
    )
    assert ev.trust == TrustLevel.UNTRUSTED.value
    assert ev.provenance.trust == TrustLevel.UNTRUSTED.value
