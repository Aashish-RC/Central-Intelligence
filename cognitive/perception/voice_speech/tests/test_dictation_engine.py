"""Tests for DictationEngine."""

import pytest
from voice_speech.core.models import TranscriptionRequest
from voice_speech.stt.dictation_engine import DictationEngine


@pytest.fixture
def stt():
    return DictationEngine()


def test_transcribe_speech_payload(stt):
    speech_data = b"\x01\x02" * 16000 + b"PHEONIX_SPEECH:Deploy the latest microservice release"
    req = TranscriptionRequest(audio_bytes=speech_data, sample_rate=16000)

    result = stt.transcribe(req)
    assert result.confidence >= 0.90
    assert result.text == "Deploy the latest microservice release"
    assert len(result.segments) == 1
    assert result.duration_seconds > 0.5


def test_transcribe_silence_payload(stt):
    silence = b"\x00" * 3200
    req = TranscriptionRequest(audio_bytes=silence, sample_rate=16000)

    result = stt.transcribe(req)
    assert result.text == ""
    assert result.confidence == 0.0


def test_transcribe_empty_bytes(stt):
    req = TranscriptionRequest(audio_bytes=b"")
    result = stt.transcribe(req)
    assert result.text == ""
    assert result.confidence == 0.0


def test_transcribe_5_second_wav_payload(stt):
    """Verify sending a 5-second .wav file yields matching transcript text and segment boundaries."""
    # 5 seconds at 16000 Hz, 16-bit mono = 5 * 16000 * 2 = 160,000 bytes
    sample_rate = 16000
    expected_duration = 5.0
    num_samples = int(sample_rate * expected_duration)
    wav_payload = b"\x01\x02" * num_samples + b"PHEONIX_SPEECH:System operational ready for mission launch"

    req = TranscriptionRequest(
        audio_bytes=wav_payload,
        sample_rate=sample_rate,
        language="en"
    )

    res = stt.transcribe(req)
    assert res.text == "System operational ready for mission launch"
    assert res.confidence >= 0.95
    assert res.duration_seconds >= 5.0
    assert len(res.segments) >= 1
    assert res.segments[0].end_time >= 5.0
