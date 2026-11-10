"""Unit tests for Cryptographic Watermarker (Features 6.31, 6.32)."""

import pytest
from cognitive.output.integrity.watermarker import CryptographicWatermarker


def test_watermark_image_and_verify_provenance():
    watermarker = CryptographicWatermarker(secret_key="unit-test-secret-key")

    # Simulate raw image bytes (e.g., standard PNG magic header + dummy payload)
    raw_image = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...image_pixel_data..."

    watermarked_image = watermarker.watermark_image(
        image_bytes=raw_image,
        creator_id="agent-007",
        model_id="flux-dev-pro",
        extra_metadata={"resolution": "1024x1024", "prompt_hash": "a1b2c3d4"},
    )

    # Invisible watermark is present
    assert len(watermarked_image) > len(raw_image)
    assert watermarked_image.startswith(raw_image)

    # Verify provenance
    result = watermarker.verify_provenance(watermarked_image)
    assert result.is_valid is True
    assert result.ai_generated is True
    assert result.payload is not None
    assert result.payload.creator_id == "agent-007"
    assert result.payload.model_id == "flux-dev-pro"
    assert result.payload.extra_metadata["resolution"] == "1024x1024"


def test_tampered_watermark_fails_verification():
    watermarker = CryptographicWatermarker(secret_key="unit-test-secret-key")
    raw_image = b"sample_image_data_stream"

    watermarked = watermarker.watermark_image(raw_image, creator_id="legit-agent")

    # Tamper with the watermark by modifying bytes near the end
    tampered = bytearray(watermarked)
    tampered[-5] ^= 0xFF  # flip bits
    tampered_bytes = bytes(tampered)

    result = watermarker.verify_provenance(tampered_bytes)
    assert result.is_valid is False
    assert result.verification_error is not None


def test_audio_watermarking():
    watermarker = CryptographicWatermarker()
    raw_audio = b"RIFF....WAVEfmt ....data....pcm_audio..."

    watermarked_audio = watermarker.watermark_audio(
        raw_audio,
        creator_id="agent-tts",
        model_id="elevenlabs-multilingual-v2",
    )

    result = watermarker.verify_provenance(watermarked_audio)
    assert result.is_valid is True
    assert result.ai_generated is True
    assert result.payload is not None
    assert result.payload.model_id == "elevenlabs-multilingual-v2"

