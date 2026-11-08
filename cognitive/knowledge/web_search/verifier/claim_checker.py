"""Source-Support & Hallucination Verifier for grounded citation checking."""

import re
from typing import List, Tuple
from urllib.parse import urlparse

from ..core.interfaces import BaseSourceVerifier
from ..core.models import ScrapedPage, SourceSupportCheck, WebCitation, utc_now


class SourceSupportVerifier(BaseSourceVerifier):
    """Verifies whether a model or agent statement is factually supported by a source web page."""

    STOPWORDS = {
        "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "from",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "it", "its", "of", "that", "this", "these", "those", "can", "could", "will", "would",
    }

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"\w+", text.lower())
        return [t for t in tokens if t not in self.STOPWORDS]

    def _split_sentences(self, text: str) -> List[str]:
        # Split on period, exclamation, question mark followed by whitespace
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in raw_sentences if len(s.strip()) > 10]

    def verify_claim(
        self,
        claim: str,
        source: ScrapedPage,
        threshold: float = 0.65,
    ) -> SourceSupportCheck:
        """Determines if claim is supported by source.clean_text."""
        claim_tokens = self._tokenize(claim)
        if not claim_tokens:
            return SourceSupportCheck(
                claim=claim,
                is_supported=False,
                support_score=0.0,
            )

        claim_set = set(claim_tokens)
        sentences = self._split_sentences(source.clean_text)

        best_score = 0.0
        best_sentence = None

        for sent in sentences:
            sent_tokens = self._tokenize(sent)
            if not sent_tokens:
                continue
            sent_set = set(sent_tokens)
            
            # Intersection ratio against claim tokens
            overlap = len(claim_set.intersection(sent_set))
            overlap_ratio = overlap / len(claim_set)

            # Check for exact phrase sequence match
            clean_claim_phrase = " ".join(claim_tokens)
            clean_sent_phrase = " ".join(sent_tokens)
            sequence_boost = 0.25 if clean_claim_phrase in clean_sent_phrase else 0.0

            total_score = min(1.0, overlap_ratio + sequence_boost)
            if total_score > best_score:
                best_score = total_score
                best_sentence = sent

        is_supported = best_score >= threshold
        citation = None

        if is_supported and best_sentence:
            domain = urlparse(source.url).netloc or "unknown-domain"
            citation = WebCitation(
                url=source.url,
                domain=domain,
                title=source.title,
                quote_text=best_sentence,
                content_sha256=source.content_sha256,
                retrieved_at=utc_now(),
            )

        return SourceSupportCheck(
            claim=claim,
            is_supported=is_supported,
            support_score=round(best_score, 4),
            supporting_quote=best_sentence if is_supported else None,
            citation=citation,
        )
