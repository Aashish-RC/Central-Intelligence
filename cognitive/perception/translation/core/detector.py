"""
Fast Unicode script and language heuristic detection engine.
"""
from __future__ import annotations

import re
from translation.core.models import LanguageCode, LocaleDetectionResult, ScriptType


class LocaleDetector:
    """Detects Unicode scripts and ISO 639-1 language codes from raw text."""

    def detect(self, text: str) -> LocaleDetectionResult:
        if not text or not text.strip():
            return LocaleDetectionResult(language=LanguageCode.EN.value, script=ScriptType.UNKNOWN, confidence=0.0)

        clean = text.strip()

        # 1. Non-Latin Unicode Script matching
        # Korean Hangul
        if re.search(r"[\uac00-\ud7af]", clean):
            return LocaleDetectionResult(language=LanguageCode.KO.value, script=ScriptType.HANGUL, confidence=0.99)

        # Japanese Hiragana / Katakana
        if re.search(r"[\u3040-\u30ff]", clean):
            return LocaleDetectionResult(language=LanguageCode.JA.value, script=ScriptType.HANZI, confidence=0.98)

        # Chinese Hanzi
        if re.search(r"[\u4e00-\u9fff]", clean):
            return LocaleDetectionResult(language=LanguageCode.ZH.value, script=ScriptType.HANZI, confidence=0.95)

        # Devanagari (Hindi)
        if re.search(r"[\u0900-\u097f]", clean):
            return LocaleDetectionResult(language=LanguageCode.HI.value, script=ScriptType.DEVANAGARI, confidence=0.99)

        # Arabic
        if re.search(r"[\u0600-\u06ff]", clean):
            return LocaleDetectionResult(language=LanguageCode.AR.value, script=ScriptType.ARABIC, confidence=0.99)

        # Cyrillic (Russian)
        if re.search(r"[\u0400-\u04ff]", clean):
            return LocaleDetectionResult(language=LanguageCode.RU.value, script=ScriptType.CYRILLIC, confidence=0.95)

        # 2. Latin token heuristics
        lower = clean.lower()
        tokens = set(re.findall(r"\b\w+\b", lower))

        es_keywords = {"hola", "gracias", "por", "favor", "buenos", "dias", "amigo", "casa", "el", "la", "como", "estas"}
        fr_keywords = {"bonjour", "merci", "oui", "salut", "monde", "le", "la", "comment", "allez", "vous"}
        de_keywords = {"hallo", "danke", "bitte", "guten", "morgen", "und", "der", "die", "das", "nicht"}

        es_matches = len(tokens.intersection(es_keywords))
        fr_matches = len(tokens.intersection(fr_keywords))
        de_matches = len(tokens.intersection(de_keywords))

        if es_matches > max(fr_matches, de_matches, 0):
            return LocaleDetectionResult(language=LanguageCode.ES.value, script=ScriptType.LATIN, confidence=0.90)
        elif fr_matches > max(es_matches, de_matches, 0):
            return LocaleDetectionResult(language=LanguageCode.FR.value, script=ScriptType.LATIN, confidence=0.90)
        elif de_matches > max(es_matches, fr_matches, 0):
            return LocaleDetectionResult(language=LanguageCode.DE.value, script=ScriptType.LATIN, confidence=0.90)

        # Default Latin English
        return LocaleDetectionResult(language=LanguageCode.EN.value, script=ScriptType.LATIN, confidence=0.85)
