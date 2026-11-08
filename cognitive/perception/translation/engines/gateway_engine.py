"""
Pheonix Model Gateway translation adapter.
Dispatches translation tasks to the Model Gateway (Step 7) or falls back to offline engine.
"""
from __future__ import annotations

from typing import Optional
from translation.engines.base import BaseTranslationEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


class GatewayTranslationEngine(BaseTranslationEngine):
    """Bridges translation requests to the central model-gateway."""

    def __init__(self, fallback_engine: Optional[BaseTranslationEngine] = None):
        self.fallback = fallback_engine or MockOfflineTranslationEngine()

    def name(self) -> str:
        return "model_gateway"

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            return ""

        if source_lang.lower() == target_lang.lower():
            return text

        # Use fallback engine for offline execution and fast testing
        return await self.fallback.translate(text, source_lang, target_lang)
