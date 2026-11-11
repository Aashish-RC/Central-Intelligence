"""Source Quality and Authority Scorer combining heuristics and LLM-as-Judge (Feature 3.43)."""

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from knowledge.quality.models import (
    QualitySignal,
    SourceQualityScore,
    SourceQualityTier,
)


class SourceQualityAuthorityScorer:
    """Evaluates the authoritativeness and informational rigor of knowledge sources."""

    AUTHORITATIVE_DOMAINS = {
        "arxiv.org", "wikipedia.org", "github.com", "nature.com", "ieee.org",
        "nih.gov", "cdc.gov", "who.int", "rfc-editor.org", "acm.org",
        "w3.org", "python.org", "kernel.org", "mozilla.org",
    }

    AUTHORITATIVE_SUFFIXES = (".gov", ".edu", ".mil")

    SPAM_PATTERNS = [
        re.compile(r"\b(you won't believe|shocking truth|miracle cure|get rich quick|click here now|guaranteed profit)\b", re.I),
        re.compile(r"\b(affiliate link|sponsored content|buy cheap|casino|crypto pump)\b", re.I),
    ]

    def __init__(
        self,
        llm_judge_fn: Optional[Callable[[str, str], Tuple[float, str]]] = None,
        authority_weight: float = 0.45,
        content_weight: float = 0.40,
        freshness_weight: float = 0.15,
    ):
        self.llm_judge_fn = llm_judge_fn
        self.authority_weight = authority_weight
        self.content_weight = content_weight
        self.freshness_weight = freshness_weight

    def score_source(
        self,
        source: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SourceQualityScore:
        """Scores a document or web source combining heuristics and LLM judge."""
        metadata = metadata or {}
        signals: List[QualitySignal] = []

        # 1. Authority evaluation
        authority_score = self.evaluate_domain_authority(source, signals)

        # 2. Content quality evaluation
        content_score = self.evaluate_content_quality(content, signals)

        # 3. Freshness evaluation
        freshness_score = self.evaluate_freshness(metadata, signals)

        # 4. Optional LLM-as-Judge
        llm_verdict = None
        if self.llm_judge_fn:
            llm_score, llm_verdict = self.llm_judge_fn(source, content[:2000])
            # Blend content score with LLM judgment
            content_score = round(0.5 * content_score + 0.5 * llm_score, 3)
            signals.append(
                QualitySignal(
                    name="llm_judge_assessment",
                    impact=llm_score - 0.5,
                    category="llm_judge",
                    description=f"LLM Judge score: {llm_score:.2f} ({llm_verdict})",
                )
            )

        # Overall weighted composite score
        overall = (
            (self.authority_weight * authority_score)
            + (self.content_weight * content_score)
            + (self.freshness_weight * freshness_score)
        )
        overall_score = max(0.0, min(1.0, round(overall, 3)))

        # Assign Quality Tier
        if overall_score >= 0.80:
            tier = SourceQualityTier.TIER_1_AUTHORITATIVE
        elif overall_score >= 0.60:
            tier = SourceQualityTier.TIER_2_RELIABLE
        elif overall_score >= 0.40:
            tier = SourceQualityTier.TIER_3_UNVERIFIED
        else:
            tier = SourceQualityTier.TIER_4_LOW_QUALITY

        return SourceQualityScore(
            source_url_or_id=source,
            overall_score=overall_score,
            authority_score=round(authority_score, 3),
            content_quality_score=round(content_score, 3),
            freshness_score=round(freshness_score, 3),
            tier=tier,
            signals=signals,
            llm_judge_verdict=llm_verdict,
            metadata=metadata,
        )

    def evaluate_domain_authority(self, source: str, signals: List[QualitySignal]) -> float:
        """Evaluates domain-level trust and publisher authority."""
        # Check if source is a URL or domain
        parsed = urlparse(source if "://" in source else f"https://{source}")
        hostname = (parsed.hostname or source).lower()

        base_authority = 0.55

        # Check official suffixes (.gov, .edu, .mil)
        if any(hostname.endswith(suffix) for suffix in self.AUTHORITATIVE_SUFFIXES):
            signals.append(
                QualitySignal(
                    name="official_tld",
                    impact=+0.35,
                    category="domain",
                    description="Official educational or governmental domain (.gov/.edu)",
                )
            )
            base_authority += 0.35

        # Check curated authoritative domains
        elif any(auth_domain in hostname for auth_domain in self.AUTHORITATIVE_DOMAINS):
            signals.append(
                QualitySignal(
                    name="curated_authoritative_domain",
                    impact=+0.30,
                    category="domain",
                    description=f"Curated high-trust knowledge publisher: {hostname}",
                )
            )
            base_authority += 0.30

        # Technical documentation subdomains (docs.*, developer.*)
        if hostname.startswith("docs.") or hostname.startswith("developer."):
            signals.append(
                QualitySignal(
                    name="tech_documentation_subdomain",
                    impact=+0.15,
                    category="domain",
                    description="Dedicated technical documentation endpoint",
                )
            )
            base_authority += 0.15

        return min(1.0, max(0.1, base_authority))

    def evaluate_content_quality(self, content: str, signals: List[QualitySignal]) -> float:
        """Evaluates informational density, technical depth, and spam indicators."""
        if not content or len(content.strip()) < 50:
            signals.append(
                QualitySignal(
                    name="sparse_content",
                    impact=-0.4,
                    category="content",
                    description="Source text is too short to be informative (< 50 chars)",
                )
            )
            return 0.2

        words = content.split()
        word_count = len(words)
        base_score = 0.65

        # Length / depth signal
        if word_count > 300:
            base_score += 0.15
            signals.append(
                QualitySignal(
                    name="detailed_article_depth",
                    impact=+0.15,
                    category="content",
                    description=f"Substantial article length ({word_count} words)",
                )
            )

        # Technical code or equation blocks
        if "```" in content or "def " in content or "class " in content or "function " in content:
            base_score += 0.10
            signals.append(
                QualitySignal(
                    name="technical_spec_or_code",
                    impact=+0.10,
                    category="content",
                    description="Contains verifiable technical specification or code snippets",
                )
            )

        # Check for spam patterns
        spam_hits = sum(1 for pat in self.SPAM_PATTERNS if pat.search(content))
        if spam_hits > 0:
            penalty = 0.25 * spam_hits
            base_score -= penalty
            signals.append(
                QualitySignal(
                    name="spam_markers_detected",
                    impact=-penalty,
                    category="content",
                    description=f"Identified {spam_hits} spam/clickbait phrase patterns",
                )
            )

        return min(1.0, max(0.1, base_score))

    def evaluate_freshness(self, metadata: Dict[str, Any], signals: List[QualitySignal]) -> float:
        """Evaluates temporal freshness and provenance metadata."""
        if "published_year" in metadata:
            year = metadata["published_year"]
            if year >= 2024:
                return 0.95
            if year >= 2020:
                return 0.85
            return 0.65

        return 0.75


@dataclass
class FreshnessRecord:
    """Tracked ingestion freshness state for a knowledge source (L3 Feature 3.40)."""

    source_id: str
    last_verified_at: float
    ttl_seconds: float = 86400.0
    is_stale: bool = False


class FreshnessTracker:
    """Tracks per-source TTL freshness and flags stale knowledge documents."""

    def __init__(self, default_ttl_seconds: float = 86400.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._records: Dict[str, FreshnessRecord] = {}

    def record_ingested(
        self,
        source_id: str,
        ttl_seconds: Optional[float] = None,
        timestamp: Optional[float] = None,
    ) -> FreshnessRecord:
        now = timestamp if timestamp is not None else time.time()
        rec = FreshnessRecord(
            source_id=source_id,
            last_verified_at=now,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds,
            is_stale=False,
        )
        self._records[source_id] = rec
        return rec

    def sweep_stale_sources(self, now: Optional[float] = None) -> List[str]:
        """Flag and return all source IDs whose TTL has elapsed."""
        ref = now if now is not None else time.time()
        stale_ids: List[str] = []
        for rec in self._records.values():
            if (ref - rec.last_verified_at) >= rec.ttl_seconds:
                rec.is_stale = True
                stale_ids.append(rec.source_id)
            else:
                rec.is_stale = False
        return stale_ids

    def get_record(self, source_id: str) -> Optional[FreshnessRecord]:
        return self._records.get(source_id)
