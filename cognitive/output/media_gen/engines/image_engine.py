"""
Image generation engine supporting Text-to-Image and Image variations.
"""
from __future__ import annotations

import hashlib
import time
from media_gen.core.models import MediaArtifact, MediaRequest, MediaType
from media_gen.engines.base import BaseMediaEngine


class ImageGenerationEngine(BaseMediaEngine):
    """Generates image artifacts from prompt instructions."""

    def supported_type(self) -> MediaType:
        return MediaType.IMAGE

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.IMAGE:
            raise ValueError(f"ImageGenerationEngine cannot handle {request.media_type}")

        width = request.parameters.get("width", 1024)
        height = request.parameters.get("height", 1024)
        steps = request.parameters.get("steps", 30)
        aspect_ratio = request.parameters.get("aspect_ratio", "1:1")

        # Deterministic synthetic PNG header and payload
        content = f"PNG_MAGIC_{request.prompt}_{width}x{height}_{steps}_{request.model}".encode("utf-8")
        raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + content
        digest = hashlib.sha256(raw_bytes).hexdigest()

        return MediaArtifact(
            request_id=request.id,
            media_type=MediaType.IMAGE,
            uri=f"file:///storage/media/images/{digest[:16]}.png",
            mime_type="image/png",
            size_bytes=len(raw_bytes),
            sha256=digest,
            metadata={
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "steps": steps,
                "model": request.model,
                "prompt": request.prompt,
            },
            created_at=time.time(),
        )
