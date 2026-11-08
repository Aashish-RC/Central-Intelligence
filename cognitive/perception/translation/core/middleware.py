"""
Conversational Auto-Translate Middleware for Bidirectional Chat, Voice, and Notifications.
"""
from __future__ import annotations

import time
from typing import Optional
from translation.core.cache import TranslationCache
from translation.core.detector import LocaleDetector
from translation.core.models import TranslationRequest, TranslationResult
from translation.engines.base import BaseTranslationEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


class AutoTranslateMiddleware:
    """Interception layer for bidirectional auto-translation across the ecosystem."""

    def __init__(
        self,
        engine: Optional[BaseTranslationEngine] = None,
        detector: Optional[LocaleDetector] = None,
        cache: Optional[TranslationCache] = None,
    ):
        self.engine = engine or MockOfflineTranslationEngine()
        self.detector = detector or LocaleDetector()
        self.cache = cache or TranslationCache()

    async def execute(self, request: TranslationRequest) -> TranslationResult:
        start_t = time.perf_counter()

        # 1. Detect source language if set to auto
        source_lang = request.source_lang
        if source_lang == "auto" or not source_lang:
            detection = self.detector.detect(request.text)
            source_lang = detection.language

        # 2. If source and target languages match, return original immediately
        if source_lang.lower() == request.target_lang.lower():
            return TranslationResult(
                request_id=request.id,
                original_text=request.text,
                translated_text=request.text,
                detected_source_lang=source_lang,
                target_lang=request.target_lang,
                engine="noop",
                cached=False,
                latency_ms=0.0,
            )

        # 3. Check cryptographic cache
        cached_entry = self.cache.get(source_lang, request.target_lang, request.text)
        if cached_entry:
            translated_text, engine_name = cached_entry
            latency_ms = (time.perf_counter() - start_t) * 1000.0
            return TranslationResult(
                request_id=request.id,
                original_text=request.text,
                translated_text=translated_text,
                detected_source_lang=source_lang,
                target_lang=request.target_lang,
                engine=engine_name,
                cached=True,
                latency_ms=latency_ms,
            )

        # 4. Perform translation
        translated_text = await self.engine.translate(request.text, source_lang, request.target_lang)

        # 5. Populate cache
        self.cache.set(source_lang, request.target_lang, request.text, translated_text, self.engine.name())

        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return TranslationResult(
            request_id=request.id,
            original_text=request.text,
            translated_text=translated_text,
            detected_source_lang=source_lang,
            target_lang=request.target_lang,
            engine=self.engine.name(),
            cached=False,
            latency_ms=latency_ms,
        )

    async def translate_inbound(self, user_text: str, agent_lang: str = "en") -> TranslationResult:
        """Translates user text to the agent's internal lingua franca."""
        req = TranslationRequest(text=user_text, target_lang=agent_lang, source_lang="auto")
        return await self.execute(req)

    async def translate_outbound(self, agent_text: str, user_lang: str, agent_lang: str = "en") -> TranslationResult:
        """Translates agent's generated response to the user's preferred locale."""
        req = TranslationRequest(text=agent_text, target_lang=user_lang, source_lang=agent_lang)
        return await self.execute(req)
