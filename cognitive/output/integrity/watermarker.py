"""Cryptographic Watermarker (Features 6.31, 6.32)

Embeds and verifies invisible cryptographic signatures and standardized "AI-generated"
provenance metadata into generated image and audio artifacts.
"""

from __future__ import annotations
import hmac
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class WatermarkPayload:
    """Standardized provenance and authenticity metadata."""
    creator_id: str
    model_id: str
    timestamp: float
    signature: str
    ai_generated: bool = True
    system_version: str = "central-intelligence-v1"
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceVerificationResult:
    """Outcome of cryptographic and metadata provenance verification."""
    is_valid: bool
    ai_generated: bool
    payload: Optional[WatermarkPayload] = None
    verification_error: Optional[str] = None


class CryptographicWatermarker:
    """Embeds and verifies cryptographic watermarks for multimedia outputs."""

    # Magic byte sequence for identifying Central Intelligence watermark chunk
    MAGIC_HEADER = b"\x00\x43\x49\x57\x4d\x00"  # \x00CIWM\x00
    DEFAULT_SECRET = "ci-quantum-provenance-secret-2026"

    def __init__(self, secret_key: str = DEFAULT_SECRET) -> None:
        self.secret_key = secret_key.encode("utf-8")

    def _generate_signature(self, creator_id: str, model_id: str, timestamp: float, metadata: Dict[str, Any]) -> str:
        data = f"{creator_id}:{model_id}:{timestamp}:{json.dumps(metadata, sort_keys=True)}"
        return hmac.new(self.secret_key, data.encode("utf-8"), hashlib.sha256).hexdigest()

    def watermark_image(
        self,
        image_bytes: bytes,
        creator_id: str = "central-intelligence-agent",
        model_id: str = "diffusion-xl",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Embed an invisible cryptographic provenance watermark into image data."""
        timestamp = time.time()
        meta = extra_metadata or {}
        sig = self._generate_signature(creator_id, model_id, timestamp, meta)

        payload = {
            "creator_id": creator_id,
            "model_id": model_id,
            "timestamp": timestamp,
            "signature": sig,
            "ai_generated": True,
            "system_version": "central-intelligence-v1",
            "extra_metadata": meta,
        }

        payload_bytes = json.dumps(payload).encode("utf-8")
        payload_len = len(payload_bytes).to_bytes(4, byteorder="big")

        # Append structured cryptographic trailer
        return image_bytes + self.MAGIC_HEADER + payload_len + payload_bytes

    def watermark_audio(
        self,
        audio_bytes: bytes,
        creator_id: str = "central-intelligence-agent",
        model_id: str = "tts-neural",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Embed an invisible cryptographic provenance watermark into audio data."""
        return self.watermark_image(audio_bytes, creator_id, model_id, extra_metadata)

    def extract_watermark(self, data: bytes) -> Optional[WatermarkPayload]:
        """Extract watermark payload from media bytes."""
        magic_pos = data.rfind(self.MAGIC_HEADER)
        if magic_pos == -1:
            return None

        pos = magic_pos + len(self.MAGIC_HEADER)
        if pos + 4 > len(data):
            return None

        payload_len = int.from_bytes(data[pos : pos + 4], byteorder="big")
        pos += 4
        if pos + payload_len > len(data):
            return None

        raw_payload = data[pos : pos + payload_len]
        try:
            parsed = json.loads(raw_payload.decode("utf-8"))
            return WatermarkPayload(
                creator_id=parsed["creator_id"],
                model_id=parsed["model_id"],
                timestamp=parsed["timestamp"],
                signature=parsed["signature"],
                ai_generated=parsed.get("ai_generated", True),
                system_version=parsed.get("system_version", "central-intelligence-v1"),
                extra_metadata=parsed.get("extra_metadata", {}),
            )
        except Exception:
            return None

    def verify_provenance(self, data: bytes) -> ProvenanceVerificationResult:
        """Verify the cryptographic signature and authenticity of watermarked media."""
        payload = self.extract_watermark(data)
        if not payload:
            return ProvenanceVerificationResult(
                is_valid=False,
                ai_generated=False,
                verification_error="No cryptographic watermark header found",
            )

        expected_sig = self._generate_signature(
            payload.creator_id,
            payload.model_id,
            payload.timestamp,
            payload.extra_metadata,
        )

        if not hmac.compare_digest(payload.signature, expected_sig):
            return ProvenanceVerificationResult(
                is_valid=False,
                ai_generated=payload.ai_generated,
                payload=payload,
                verification_error="Cryptographic signature mismatch: artifact tampered or modified",
            )

        return ProvenanceVerificationResult(
            is_valid=True,
            ai_generated=payload.ai_generated,
            payload=payload,
        )

