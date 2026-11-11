"""Intra-Sentence Code-Switching Transcription Handler (L1 Feature 1.26)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cognitive.perception.translation.core.detector import LocaleDetector


@dataclass
class CodeSwitchSpan:
    """Contiguous token span sharing a detected language."""

    text: str
    language: str
    start_token: int
    end_token: int


@dataclass
class CodeSwitchResult:
    """Normalized mixed-language transcript with per-span language annotations."""

    transcript: str
    primary_language: str
    languages_present: List[str] = field(default_factory=list)
    spans: List[CodeSwitchSpan] = field(default_factory=list)


_LEXICON_HINTS: Dict[str, str] = {
    # Spanish common code-switched lemmas
    "comprar": "es", "necesito": "es", "pero": "es", "vamos": "es", "mañana": "es", "casa": "es",
    "trabajo": "es", "amigo": "es", "bueno": "es", "gracias": "es",
    # French
    "merci": "fr", "bonjour": "fr", "demain": "fr", "avec": "fr", "très": "fr",
    # German
    "danke": "de", "morgen": "de", "bitte": "de", "arbeit": "de",
    # Hindi romanized
    "acha": "hi", "yaar": "hi", "chalo": "hi", "kal": "hi",
}

# Phonetic/ASR repair table when monolingual decoding mangles foreign intra-sentence words
_PHONETIC_REPAIRS: Dict[str, str] = {
    "comprah": "comprar",
    "komprar": "comprar",
    "mercy": "merci",
}


class CodeSwitchingHandler:
    """Segments mixed-language utterances and preserves non-primary tokens accurately."""

    def __init__(self, primary_language: str = "en") -> None:
        self.primary_language = primary_language
        self._locale_detector = LocaleDetector()

    def _classify_token(self, token: str) -> str:
        cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", token, flags=re.UNICODE).lower()
        if not cleaned:
            return self.primary_language
        if cleaned in _LEXICON_HINTS:
            return _LEXICON_HINTS[cleaned]
        # Check non-Latin script directly
        if any(ord(ch) > 127 for ch in cleaned):
            res = self._locale_detector.detect(cleaned)
            if res.script != "Latin":
                return res.language
        return self.primary_language

    def normalize_mixed_utterance(
        self,
        raw_transcript: str,
        secondary_language: Optional[str] = None,
    ) -> CodeSwitchResult:
        tokens = raw_transcript.split()
        repaired_tokens: List[str] = []
        spans: List[CodeSwitchSpan] = []

        current_lang: Optional[str] = None
        span_start = 0
        span_tokens: List[str] = []

        for idx, tok in enumerate(tokens):
            low = tok.strip(".,!?").lower()
            if low in _PHONETIC_REPAIRS:
                tok = _PHONETIC_REPAIRS[low]
            lang = self._classify_token(tok)
            if secondary_language and lang != self.primary_language and lang == "und":
                lang = secondary_language
            repaired_tokens.append(tok)

            if current_lang is None:
                current_lang = lang
                span_start = idx
                span_tokens = [tok]
            elif lang == current_lang:
                span_tokens.append(tok)
            else:
                spans.append(
                    CodeSwitchSpan(
                        text=" ".join(span_tokens),
                        language=current_lang,
                        start_token=span_start,
                        end_token=idx,
                    )
                )
                current_lang = lang
                span_start = idx
                span_tokens = [tok]

        if current_lang is not None and span_tokens:
            spans.append(
                CodeSwitchSpan(
                    text=" ".join(span_tokens),
                    language=current_lang,
                    start_token=span_start,
                    end_token=len(repaired_tokens),
                )
            )

        langs: List[str] = []
        for s in spans:
            if s.language not in langs:
                langs.append(s.language)
        return CodeSwitchResult(
            transcript=" ".join(repaired_tokens),
            primary_language=self.primary_language,
            languages_present=langs or [self.primary_language],
            spans=spans,
        )

