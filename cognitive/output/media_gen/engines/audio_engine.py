"""
Audio and sound generation engine supporting Sound Effects and Music tracks.
"""
from __future__ import annotations

import hashlib
import time
from media_gen.core.models import MediaArtifact, MediaRequest, MediaType
from media_gen.engines.base import BaseMediaEngine


class AudioGenerationEngine(BaseMediaEngine):
    """Generates audio artifacts from text descriptions."""

    def supported_type(self) -> MediaType:
        return MediaType.AUDIO

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.AUDIO:
            raise ValueError(f"AudioGenerationEngine cannot handle {request.media_type}")

        duration = request.parameters.get("duration_seconds", 10.0)
        sample_rate = request.parameters.get("sample_rate", 44100)
        channels = request.parameters.get("channels", 2)

        # Deterministic synthetic RIFF/WAVE header and audio payload
        content = f"WAV_DATA_{request.prompt}_{duration}s_{sample_rate}Hz".encode("utf-8")
        raw_bytes = b"RIFF" + (36 + len(content)).to_bytes(4, "little") + b"WAVEfmt " + content
        digest = hashlib.sha256(raw_bytes).hexdigest()

        return MediaArtifact(
            request_id=request.id,
            media_type=MediaType.AUDIO,
            uri=f"file:///storage/media/audio/{digest[:16]}.wav",
            mime_type="audio/wav",
            size_bytes=len(raw_bytes),
            sha256=digest,
            metadata={
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "model": request.model,
                "prompt": request.prompt,
            },
            created_at=time.time(),
        )
