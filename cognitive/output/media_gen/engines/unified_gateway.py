"""
Unified Media Gateway and multi-provider connector.
Routes generation requests to specialized modal engines (Image, Audio, Video) or external providers (Eden AI).
"""
from __future__ import annotations

from typing import Dict
from media_gen.core.models import MediaArtifact, MediaRequest, MediaType
from media_gen.engines.audio_engine import AudioGenerationEngine
from media_gen.engines.base import BaseMediaEngine
from media_gen.engines.image_engine import ImageGenerationEngine
from media_gen.engines.video_engine import VideoGenerationEngine


class UnifiedMediaGateway:
    """Multi-modal gateway router with engine registration and dispatch."""

    def __init__(self):
        self._engines: Dict[MediaType, BaseMediaEngine] = {
            MediaType.IMAGE: ImageGenerationEngine(),
            MediaType.AUDIO: AudioGenerationEngine(),
            MediaType.VIDEO: VideoGenerationEngine(),
        }

    def register_engine(self, engine: BaseMediaEngine) -> None:
        self._engines[engine.supported_type()] = engine

    def get_engine(self, media_type: MediaType) -> BaseMediaEngine:
        if media_type not in self._engines:
            raise ValueError(f"No generation engine registered for {media_type}")
        return self._engines[media_type]

    async def dispatch(self, request: MediaRequest) -> MediaArtifact:
        engine = self.get_engine(request.media_type)
        return await engine.generate(request)
