"""
Video generation engine supporting Text-to-Video and Motion synthesis.
"""
from __future__ import annotations

import hashlib
import time
from media_gen.core.models import MediaArtifact, MediaRequest, MediaType
from media_gen.engines.base import BaseMediaEngine


class VideoGenerationEngine(BaseMediaEngine):
    """Generates video artifacts from text prompts or keyframes."""

    def supported_type(self) -> MediaType:
        return MediaType.VIDEO

    async def generate(self, request: MediaRequest) -> MediaArtifact:
        if request.media_type != MediaType.VIDEO:
            raise ValueError(f"VideoGenerationEngine cannot handle {request.media_type}")

        duration = request.parameters.get("duration_seconds", 4.0)
        fps = request.parameters.get("fps", 24)
        motion_bucket = request.parameters.get("motion_bucket", 127)

        # Deterministic synthetic MP4 container header and payload
        content = f"MP4_DATA_{request.prompt}_{duration}s_{fps}fps_motion{motion_bucket}".encode("utf-8")
        raw_bytes = b"\x00\x00\x00\x20ftypisom" + content
        digest = hashlib.sha256(raw_bytes).hexdigest()

        return MediaArtifact(
            request_id=request.id,
            media_type=MediaType.VIDEO,
            uri=f"file:///storage/media/videos/{digest[:16]}.mp4",
            mime_type="video/mp4",
            size_bytes=len(raw_bytes),
            sha256=digest,
            metadata={
                "duration_seconds": duration,
                "fps": fps,
                "motion_bucket": motion_bucket,
                "model": request.model,
                "prompt": request.prompt,
            },
            created_at=time.time(),
        )
