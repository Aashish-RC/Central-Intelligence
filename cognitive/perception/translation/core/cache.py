"""
Cryptographic translation cache with SHA-256 deterministic keying and telemetry.
"""
from __future__ import annotations

import hashlib
import threading
from typing import Dict, Optional, Tuple


class TranslationCache:
    """Thread-safe translation result cache keyed by cryptographic content hash."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._cache: Dict[str, Tuple[str, str]] = {}  # key -> (translated_text, engine)
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _make_key(self, source_lang: str, target_lang: str, text: str) -> str:
        composite = f"{source_lang.lower().strip()}:{target_lang.lower().strip()}:{text.strip()}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()

    def get(self, source_lang: str, target_lang: str, text: str) -> Optional[Tuple[str, str]]:
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if key in self._cache:
                self.hits += 1
                return self._cache[key]
            self.misses += 1
            return None

    def set(self, source_lang: str, target_lang: str, text: str, translated_text: str, engine: str) -> None:
        key = self._make_key(source_lang, target_lang, text)
        with self._lock:
            if len(self._cache) >= self.max_entries:
                # Evict oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[key] = (translated_text, engine)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def size(self) -> int:
        with self._lock:
            return len(self._cache)
