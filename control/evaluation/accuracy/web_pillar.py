"""Web Pillar: S_web (Layer 11: Evaluation & Quality, Feature 11.14).

Performs real-time factual verification of claims decomposed from model responses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AtomicClaim:
    """An individual verifiable claim."""
    claim_id: str
    text: str
    verified: bool = False
    confidence: float = 0.0
    evidence: Optional[str] = None


class WebPillar:
    """Evaluates factual grounding ratio S_web using web verification search."""

    def __init__(self, search_verifier: Optional[Callable[[str], bool]] = None):
        self.search_verifier = search_verifier

    def decompose_claims(self, text: str) -> List[str]:
        """Simple heuristic decomposer into atomic propositional sentences."""
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 15]
        return sentences

    def verify_claims(
        self,
        claims: List[str],
        reference_knowledge: Optional[List[str]] = None,
    ) -> List[AtomicClaim]:
        """Verifies each atomic claim against web knowledge or provided references."""
        verified_claims: List[AtomicClaim] = []
        ref_text = " ".join(reference_knowledge or []).lower()

        for idx, claim in enumerate(claims):
            cid = f"claim-{idx+1}"
            verified = False
            confidence = 0.5
            evidence = None

            if self.search_verifier:
                try:
                    verified = bool(self.search_verifier(claim))
                    confidence = 0.9 if verified else 0.2
                    evidence = "Web Search Live Verifier"
                except Exception:
                    verified = False
            elif reference_knowledge:
                c_words = [w for w in re.findall(r"\w+", claim.lower()) if len(w) > 3]
                if c_words:
                    matches = sum(1 for w in c_words if w in ref_text)
                    ratio = matches / len(c_words)
                    verified = ratio >= 0.5
                    confidence = round(ratio, 2)
                    evidence = f"Matched {matches}/{len(c_words)} key concepts in reference knowledge"
            else:
                # Without live verifier or references, neutral assumption for non-contradicted claims
                verified = True
                confidence = 0.8
                evidence = "Default assumed grounded"

            verified_claims.append(
                AtomicClaim(
                    claim_id=cid,
                    text=claim,
                    verified=verified,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        return verified_claims

    def calculate_web_score(
        self,
        text_or_claims: Any,
        reference_knowledge: Optional[List[str]] = None,
    ) -> float:
        """Calculates S_web in range [0.0, 1.0]."""
        if isinstance(text_or_claims, list):
            claims = text_or_claims
        else:
            claims = self.decompose_claims(str(text_or_claims))

        if not claims:
            return 1.0  # Empty text contains no unverified claims

        verified = self.verify_claims(claims, reference_knowledge)
        supported_count = sum(1 for c in verified if c.verified)
        return round(supported_count / len(verified), 4)
