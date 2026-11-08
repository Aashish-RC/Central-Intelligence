"""
Offline Machine Translation Adapter (Task 6.5).
Provides unified offline machine translation with automatic language detection,
in-memory caching, and local LibreTranslate container / offline lexicon support.
"""
from __future__ import annotations

import asyncio
from typing import Optional
import httpx
from translation.core.cache import TranslationCache
from translation.core.detector import LocaleDetector
from translation.core.models import LanguageCode
from translation.engines.libre_engine import LibreTranslateEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


class OfflineTranslationEngine:
    """
    Offline machine translation engine integrating automatic language detection,
    LRU caching, and LibreTranslate / deterministic offline models.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        gateway_url: Optional[str] = None,
        cache_capacity: int = 1000,
        detector: Optional[LocaleDetector] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.detector = detector or LocaleDetector()
        self.cache = TranslationCache(max_entries=cache_capacity)
        self.backend = LibreTranslateEngine(
            endpoint_url=endpoint_url,
            gateway_url=gateway_url,
            fallback=MockOfflineTranslationEngine(),
            http_client=http_client,
        )

    async def translate_async(
        self,
        text: str,
        target: str = "en",
        source: Optional[str] = None
    ) -> str:
        """
        Translates text to target language asynchronously with automatic detection and caching.
        """
        if not text or not text.strip():
            return ""

        clean = text.strip()
        target_norm = target.lower().strip()

        # 1. Detect source language if not specified
        if not source:
            detected = self.detector.detect(clean)
            source_norm = detected.language
        else:
            source_norm = source.lower().strip()

        # 2. No-op if source equals target
        if source_norm == target_norm:
            return clean

        # 3. Check cache
        cached = self.cache.get(source_norm, target_norm, clean)
        if cached is not None:
            return cached[0]

        # 4. Perform translation via backend adapter
        translated = await self.backend.translate(clean, source_norm, target_norm)

        # 5. Populate cache
        self.cache.set(source_norm, target_norm, clean, translated, self.backend.name())
        return translated

    def translate(
        self,
        text: str,
        target: str = "en",
        source: Optional[str] = None
    ) -> str:
        """
        Synchronous convenience translation method.
        Done when: translate("Bonjour", target="en") returns "Hello".
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.translate_async(text, target=target, source=source))
        else:
            return asyncio.run(self.translate_async(text, target=target, source=source))


# Global default instance
_default_engine = OfflineTranslationEngine()


def translate(
    text: str,
    target: str = "en",
    source: Optional[str] = None
) -> str:
    """
    Top-level translation function.
    Done when: translate("Bonjour", target="en") returns "Hello".
    """
    return _default_engine.translate(text, target=target, source=source)
