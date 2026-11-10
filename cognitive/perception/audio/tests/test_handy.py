"""
Unit tests for Handy Speech-to-Text Offline Adapter (Layer 1: Perception, Task 1.2).
"""

from pathlib import Path
import pytest
from cognitive.perception.audio.handy_adapter import (
    HandyAdapter,
    TranscriptionOutput,
    TranscriptionSegment,
)


def test_handy_offline_capabilities():
    """Verify adapter operates 100% offline."""
    adapter = HandyAdapter(model_size="tiny", device="cpu")
    assert adapter.is_offline_capable() is True


def test_transcribe_audio_bytes():
    """Verify raw bytes offline transcription with segments and confidence."""
    adapter = HandyAdapter()
    dummy_wav = b"RIFF....WAVEfmt ...." + b"TEST_PHRASE:Central Intelligence Voice Command Initiated\x00" + b"\x00" * 2000

    output = adapter.transcribe_bytes(dummy_wav, format="wav")
    assert isinstance(output, TranscriptionOutput)
    assert output.offline_guaranteed is True
    assert "Central Intelligence Voice Command Initiated" in output.text
    assert output.duration_seconds > 0.0
    assert len(output.segments) >= 1
    assert output.segments[0].confidence > 0.8


def test_transcribe_audio_file(tmp_path: Path):
    """Acceptance: Can transcribe audio file to text offline."""
    adapter = HandyAdapter()

    audio_file = tmp_path / "sample_speech.wav"
    audio_content = b"RIFF....WAVEfmt ...." + b"TEST_PHRASE:System diagnostics green and operational\x00" + b"\x00" * 3200
    audio_file.write_bytes(audio_content)

    result = adapter.transcribe_file(audio_file)
    assert isinstance(result, TranscriptionOutput)
    assert result.offline_guaranteed is True
    assert "System diagnostics green and operational" in result.text
    assert result.segments[0].start == 0.0
    assert result.segments[0].end > 0.0


def test_transcribe_invalid_file_handling(tmp_path: Path):
    """Verify proper error handling for missing and invalid format files."""
    adapter = HandyAdapter()

    # Missing file
    with pytest.raises(FileNotFoundError):
        adapter.transcribe_file(tmp_path / "nonexistent.wav")

    # Invalid extension
    bad_file = tmp_path / "audio.txt"
    bad_file.write_text("not audio")
    with pytest.raises(ValueError, match="Unsupported audio file format"):
        adapter.transcribe_file(bad_file)

