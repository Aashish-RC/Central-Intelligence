"""Custom Domain Vocabulary Biasing for Speech-to-Text (L1 Feature 1.24)."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class VocabularyBiasProfile:
    """Domain lexicon with optional phonetic/spelling typo overrides."""

    domain: str
    terms: List[str] = field(default_factory=list)
    phonetic_aliases: Dict[str, str] = field(default_factory=dict)


class CustomVocabularyBiaser:
    """Builds Whisper initial_prompt hints and corrects near-homophone transcript errors."""

    def __init__(self, similarity_threshold: float = 0.78) -> None:
        self.similarity_threshold = similarity_threshold
        self._terms: Dict[str, str] = {}  # lower -> canonical casing
        self._aliases: Dict[str, str] = {}

    def register_terms(self, terms: Iterable[str]) -> None:
        for t in terms:
            cleaned = t.strip()
            if cleaned:
                self._terms[cleaned.lower()] = cleaned

    def register_alias(self, misheard: str, canonical: str) -> None:
        self._aliases[misheard.strip().lower()] = canonical.strip()

    def build_whisper_prompt(self, max_terms: int = 50) -> str:
        """Return an initial prompt string for biasing Whisper decoding."""
        selected = list(self._terms.values())[:max_terms]
        return "Domain vocabulary: " + ", ".join(selected) if selected else ""

    @staticmethod
    def _soundex(word: str) -> str:
        w = re.sub(r"[^a-z]", "", word.lower())
        if not w:
            return ""
        mapping = {
            "b": "1", "f": "1", "p": "1", "v": "1",
            "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
            "d": "3", "t": "3",
            "l": "4",
            "m": "5", "n": "5",
            "r": "6",
        }
        code = [w[0].upper()]
        prev = mapping.get(w[0], "")
        for ch in w[1:]:
            digit = mapping.get(ch, "")
            if digit and digit != prev:
                code.append(digit)
            prev = digit
            if len(code) == 4:
                break
        return "".join(code).ljust(4, "0")

    def apply_correction(self, transcript: str) -> str:
        """Snap near-homophone or misspelled domain tokens in ``transcript`` to registered terms."""
        if not self._terms and not self._aliases:
            return transcript

        def _replace(match: re.Match[str]) -> str:
            token = match.group(0)
            low = token.lower()
            if low in self._aliases:
                return self._aliases[low]
            if low in self._terms:
                return self._terms[low]
            if len(low) < 4:
                return token

            tok_sx = self._soundex(low)
            best_term: Optional[str] = None
            best_score = 0.0
            for t_low, canonical in self._terms.items():
                if abs(len(t_low) - len(low)) > 3:
                    continue
                ratio = difflib.SequenceMatcher(None, low, t_low).ratio()
                if self._soundex(t_low) == tok_sx:
                    ratio = max(ratio, ratio + 0.08)
                if ratio >= self.similarity_threshold and ratio > best_score:
                    best_score = ratio
                    best_term = canonical
            return best_term or token

        return re.sub(r"[A-Za-z][A-Za-z0-9'-]*", _replace, transcript)

