"""Unit and live tests for SpeechSynthesizer routing to Model Gateway /v1/audio/speech."""
import json
import os
import struct
import pytest
import httpx

from voice_speech.core.models import AudioFormat, SpeechSynthesisRequest
from voice_speech.tts.synthesis_engine import SpeechSynthesizer


def _make_dummy_wav_bytes() -> bytes:
    """Build a minimal valid 44-byte RIFF WAV file."""
    pcm_data = b"\x00\x10" * 240
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm_data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        24000,
        48000,
        2,
        16,
        b"data",
        len(pcm_data),
    )
    return header + pcm_data


@pytest.fixture
def fake_gateway_tts_transport():
    """Fake transport simulating the Model Gateway TTS endpoint."""
    captured_requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path.endswith("/v1/audio/speech"):
            body = json.loads(request.content.decode("utf-8"))
            if not body.get("input"):
                return httpx.Response(400, json={"error": "Missing input"})
            return httpx.Response(
                200,
                content=_make_dummy_wav_bytes(),
                headers={"content-type": "audio/wav"},
            )
        return httpx.Response(404, json={"error": "Not found"})

    transport = httpx.MockTransport(handle_request)
    transport.captured_requests = captured_requests
    return transport


def test_tts_routes_to_gateway_with_fake_transport(fake_gateway_tts_transport):
    """Verify that SpeechSynthesizer posts correctly to /v1/audio/speech via fake transport."""
    client = httpx.Client(transport=fake_gateway_tts_transport)
    synthesizer = SpeechSynthesizer(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    req = SpeechSynthesisRequest(
        text="The quick brown fox jumps over the lazy dog.",
        speed=1.0,
        audio_format=AudioFormat.WAV,
    )
    result = synthesizer.synthesize(req)

    assert result.audio_format == AudioFormat.WAV
    assert len(result.audio_bytes) > 44
    assert result.audio_bytes[:4] == b"RIFF"
    assert result.audio_bytes[8:12] == b"WAVE"
    assert len(fake_gateway_tts_transport.captured_requests) == 1

    last_req = fake_gateway_tts_transport.captured_requests[0]
    assert last_req.url.path == "/v1/audio/speech"
    data = json.loads(last_req.content.decode("utf-8"))
    assert data["input"] == "The quick brown fox jumps over the lazy dog."
    assert data["model"] == "tts-1"


def test_tts_falls_back_when_gateway_returns_invalid_wav():
    def invalid_audio_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"RIFF-AUDIO-STREAM-FORMAT:wav")

    client = httpx.Client(transport=httpx.MockTransport(invalid_audio_handler))
    synthesizer = SpeechSynthesizer(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    result = synthesizer.synthesize("Fallback after invalid gateway audio")

    assert result.audio_bytes[:4] == b"RIFF"
    assert result.audio_bytes[8:12] == b"WAVE"
    assert result.audio_bytes != b"RIFF-AUDIO-STREAM-FORMAT:wav"


def test_tts_stream_with_fake_transport(fake_gateway_tts_transport):
    """Verify stream synthesis produces valid chunked bytes using fake gateway transport."""
    client = httpx.Client(transport=fake_gateway_tts_transport)
    synthesizer = SpeechSynthesizer(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    chunks = list(synthesizer.synthesize_stream("Realtime speech chunking test", chunk_size=128))
    assert len(chunks) >= 2
    full_audio = b"".join(chunks)
    assert full_audio[:4] == b"RIFF"


def test_tts_gateway_error_raises_with_injected_client():
    """Verify HTTP errors bubble up when a custom client is provided."""
    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Gateway internal failure"})

    fake_failing_transport = httpx.MockTransport(error_handler)
    client = httpx.Client(transport=fake_failing_transport)
    synthesizer = SpeechSynthesizer(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    with pytest.raises(httpx.HTTPStatusError):
        synthesizer.synthesize("Failure expected")


def test_tts_fallback_to_local_wav_when_no_client_and_gateway_offline():
    """Verify clean local fallback to synthetic RIFF WAV when gateway is unreachable."""
    synthesizer = SpeechSynthesizer(
        gateway_url="http://127.0.0.1:59999",  # unreachable port
        http_client=None,
    )
    res = synthesizer.synthesize("Local fallback synthesis test")
    assert res.audio_bytes[:4] == b"RIFF"
    assert res.audio_bytes[8:12] == b"WAVE"
    assert res.duration_seconds > 0.0


@pytest.mark.live
def test_tts_gateway_live():
    """Live test against running Model Gateway service."""
    if os.getenv("PHEONIX_LIVE") != "1":
        pytest.skip("PHEONIX_LIVE is not enabled (set PHEONIX_LIVE=1)")

    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:4000")
    try:
        ping = httpx.get(f"{gateway_url}/health", timeout=2.0)
        if ping.status_code != 200:
            pytest.skip(f"Live gateway service unhealthy at {gateway_url}")
    except Exception as exc:
        pytest.skip(f"Live gateway service not reachable at {gateway_url}: {exc}")

    synthesizer = SpeechSynthesizer(gateway_url=gateway_url)
    res = synthesizer.synthesize("Live integration verification for TTS gateway routing.")
    assert len(res.audio_bytes) > 0
