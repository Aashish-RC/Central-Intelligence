"""
Base abstract translation engine class.
"""
from __future__ import annotations

import abc


class BaseTranslationEngine(abc.ABC):
    """Abstract base class for translation backend providers."""

    @abc.abstractmethod
    def name(self) -> str:
        """Returns the unique identifier for this translation engine."""
        pass

    @abc.abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translates text from source language to target language."""
        pass
