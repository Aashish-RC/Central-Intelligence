"""Surgical Claim Diff Patcher (Feature 6.37)

When L11 (Alignment/Safety/Verification) flags a refuted claim in generated text,
this module surgically patches ONLY the refuted sentences without invalidating or
re-streaming the entire verified document.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RefutedClaim:
    """Represents a factual or safety claim refuted by verification engines."""
    id: str
    text: str
    refutation_reason: str = ""
    severity: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimPatchResult:
    """Detailed summary of surgical patch operations."""
    patched_text: str
    replaced_count: int
    unchanged_count: int
    patches: List[Dict[str, Any]] = field(default_factory=list)


class ClaimDiffPatcher:
    """Surgically patches refuted claims into streamable document representations."""

    def __init__(self) -> None:
        # Regex to split text into sentences while retaining terminal punctuation
        self._sentence_split_regex = re.compile(r'(?<=[.!?])\s+')

    def split_sentences(self, text: str) -> List[str]:
        """Split a text blob into individual sentences."""
        if not text or not text.strip():
            return []
        sentences = self._sentence_split_regex.split(text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def patch(
        self,
        original_text: str,
        refuted_claims: List[RefutedClaim],
        corrections: Dict[str, str],
    ) -> str:
        """Surgically replace only the refuted sentences. Rest remains unchanged."""
        result = self.patch_with_details(original_text, refuted_claims, corrections)
        return result.patched_text

    def patch_with_details(
        self,
        original_text: str,
        refuted_claims: List[RefutedClaim],
        corrections: Dict[str, str],
    ) -> ClaimPatchResult:
        """Perform surgical patching and record sentence-level audit trails."""
        sentences = self.split_sentences(original_text)
        replaced_count = 0
        unchanged_count = 0
        patches: List[Dict[str, Any]] = []

        for i, sentence in enumerate(sentences):
            matched = False
            for claim in refuted_claims:
                if claim.text in sentence and claim.id in corrections:
                    replacement = corrections[claim.id]
                    patches.append({
                        "sentence_index": i,
                        "claim_id": claim.id,
                        "original_sentence": sentence,
                        "patched_sentence": replacement,
                        "refutation_reason": claim.refutation_reason,
                    })
                    sentences[i] = replacement
                    replaced_count += 1
                    matched = True
                    break
            if not matched:
                unchanged_count += 1

        patched_text = " ".join(sentences)
        return ClaimPatchResult(
            patched_text=patched_text,
            replaced_count=replaced_count,
            unchanged_count=unchanged_count,
            patches=patches,
        )
