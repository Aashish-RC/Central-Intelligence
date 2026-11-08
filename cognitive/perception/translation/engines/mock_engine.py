"""
Mock and offline deterministic translation engine for zero-dependency CI and tests.
"""
from __future__ import annotations

from typing import Dict, Tuple
from translation.engines.base import BaseTranslationEngine


# Deterministic lexicon map (source_text.lower(), target_lang) -> translated_text
LEXICON: Dict[Tuple[str, str], str] = {
    ("hello", "es"): "Hola",
    ("hello", "fr"): "Bonjour",
    ("hello", "de"): "Hallo",
    ("hello", "zh"): "你好",
    ("hello", "ja"): "こんにちは",
    ("hello", "ko"): "안녕하세요",
    ("hello", "hi"): "नमस्ते",
    ("hello", "ar"): "مرحبا",
    ("hello", "ru"): "Здравствуйте",
    ("good morning", "es"): "Buenos días",
    ("good morning", "fr"): "Bonjour",
    ("good morning", "de"): "Guten Morgen",
    ("good morning", "zh"): "早上好",
    ("thank you", "es"): "Gracias",
    ("thank you", "fr"): "Merci",
    ("thank you", "de"): "Danke",
    ("thank you", "zh"): "谢谢",
    ("thank you", "ja"): "ありがとう",
    ("thank you", "ko"): "감사합니다",
    ("thank you", "hi"): "धन्यवाद",
    ("how are you?", "es"): "¿Cómo estás?",
    ("how are you?", "fr"): "Comment allez-vous?",
    ("how are you?", "de"): "Wie geht es dir?",
    ("how are you?", "zh"): "你好吗？",
    ("hola", "en"): "Hello",
    ("gracias", "en"): "Thank you",
    ("bonjour", "en"): "Hello",
    ("merci", "en"): "Thank you",
    ("hallo", "en"): "Hello",
    ("danke", "en"): "Thank you",
    ("你好", "en"): "Hello",
    ("谢谢", "en"): "Thank you",
    ("नमस्ते", "en"): "Hello",
    ("धन्यवाद", "en"): "Thank you",
}


class MockOfflineTranslationEngine(BaseTranslationEngine):
    """Deterministic offline translation engine."""

    def name(self) -> str:
        return "mock_offline"

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            return ""

        if source_lang.lower() == target_lang.lower():
            return text

        clean = text.strip()
        lower_key = clean.lower()

        # Check lexicon
        if (lower_key, target_lang.lower()) in LEXICON:
            return LEXICON[(lower_key, target_lang.lower())]

        # Deterministic simulation for arbitrary phrases
        return f"[{target_lang.upper()}] {clean}"
