"""64-bit SimHash Near-Duplicate Document Deduplicator (L3 Feature 3.16)."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Optional, Tuple


_WORD_RE = re.compile(r"[a-z0-9]+")


class SimHashDeduplicator:
    """Detects exact and near-duplicate documents using 64-bit token SimHash."""

    def __init__(self, max_hamming_distance: int = 6) -> None:
        self.max_hamming_distance = max_hamming_distance
        self._fingerprints: Dict[str, int] = {}

    @staticmethod
    def compute_simhash(text: str) -> int:
        tokens = _WORD_RE.findall(text.lower())
        if not tokens:
            return 0
        features = list(tokens) + [" ".join(tokens[i : i + 2]) for i in range(len(tokens) - 1)]
        v = [0] * 64
        for feat in features:
            h = int.from_bytes(hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest(), "big")
            for bit in range(64):
                v[bit] += 1 if (h >> bit) & 1 else -1
        fingerprint = 0
        for bit in range(64):
            if v[bit] > 0:
                fingerprint |= 1 << bit
        return fingerprint

    @staticmethod
    def hamming_distance(a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def register_or_check(self, doc_id: str, text: str) -> Tuple[bool, Optional[str]]:
        """Return `(is_duplicate, matched_doc_id)` and register unique docs."""
        fp = self.compute_simhash(text)
        for existing_id, existing_fp in self._fingerprints.items():
            if self.hamming_distance(fp, existing_fp) <= self.max_hamming_distance:
                return True, existing_id
        self._fingerprints[doc_id] = fp
        return False, None
