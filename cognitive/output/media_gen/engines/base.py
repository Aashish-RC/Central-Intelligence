"""
Base abstract class for media generation engines.
"""
from __future__ import annotations

import abc
from media_gen.core.models import MediaArtifact, MediaRequest, MediaType


class BaseMediaEngine(abc.ABC):
    """Abstract base class for modal generation engines."""

    @abc.abstractmethod
    def supported_type(self) -> MediaType:
        """Returns the media type this engine handles."""
        pass

    @abc.abstractmethod
    async def generate(self, request: MediaRequest) -> MediaArtifact:
        """Generates media artifact asynchronously from request."""
        pass
