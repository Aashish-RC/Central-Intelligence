"""Decay & Compression Policy Engine.

Provides automated memory lifecycle management:
- Exponential decay scoring with access reinforcement (Feature 2.13)
- Multi-tier semantic compression and episodic rollup (Feature 2.39)
- Soft decay pruning and tombstone purges for obsolete facts (Feature 2.40)

Features: 2.13, 2.39, 2.40
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set
from memory.core.models import FactCategory, FactItem, MemoryRecord, utc_now


@dataclass
class MemoryDecayPolicy:
    """Configurable thresholds governing fact decay and episodic compression."""
    half_life_days: float = 30.0
    prune_threshold: float = 0.15
    compression_threshold_tokens: int = 1500
    frequency_bonus_weight: float = 1.0
    # Permanent categories that never decay
    exempt_categories: Set[FactCategory] = field(
        default_factory=lambda: {FactCategory.RULE, FactCategory.CONSTRAINT}
    )


class DecayCompressionPolicyEngine:
    """Evaluates and executes decay degradation, tombstoning, and episodic compression."""

    def __init__(self, policy: Optional[MemoryDecayPolicy] = None):
        self.policy = policy or MemoryDecayPolicy()

    def calculate_relevance_score(
        self,
        last_accessed_at: datetime,
        base_confidence: float = 1.0,
        access_count: int = 0,
        category: Optional[FactCategory] = None,
    ) -> float:
        """Calculates current decayed relevance score for a memory item.
        
        Permanent rules and constraints are exempt and always return 1.0.
        """
        if category in self.policy.exempt_categories:
            return 1.0

        now = utc_now()
        if last_accessed_at.tzinfo is None:
            last_accessed_at = last_accessed_at.replace(tzinfo=timezone.utc)

        elapsed_seconds = max(0.0, (now - last_accessed_at).total_seconds())
        elapsed_days = elapsed_seconds / 86400.0

        # Exponential decay factor: 0.5 ^ (elapsed_days / half_life)
        decay = math.pow(0.5, elapsed_days / max(0.1, self.policy.half_life_days))

        # Frequency reinforcement: frequently retrieved memories resist decay
        freq_bonus = math.log2(2.0 + (access_count * self.policy.frequency_bonus_weight))

        score = base_confidence * decay * freq_bonus
        return float(min(1.0, max(0.0, score)))

    def identify_prune_candidates(self, facts: List[FactItem]) -> List[FactItem]:
        """Filters facts whose decayed relevance falls below the configured prune threshold."""
        prune_list: List[FactItem] = []

        for f in facts:
            # Exempt categories are never pruned
            if f.category in self.policy.exempt_categories:
                continue

            last_active = getattr(f, "last_accessed_at", f.updated_at)
            accesses = getattr(f, "access_count", 0)
            conf = getattr(f, "confidence_score", getattr(f, "confidence", 1.0))
            score = self.calculate_relevance_score(
                last_accessed_at=last_active,
                base_confidence=conf,
                access_count=accesses,
                category=f.category,
            )

            if score < self.policy.prune_threshold:
                prune_list.append(f)

        return prune_list

    def compress_episodes(
        self,
        records: List[MemoryRecord],
        target_token_budget: int = 400,
    ) -> Dict[str, Any]:
        """Compresses multiple historical memory records into a dense episodic rollup milestone."""
        if not records:
            return {"summary": "", "records_compressed": 0, "token_estimate": 0}

        sorted_records = sorted(records, key=lambda r: r.created_at)
        bullet_points = []

        for r in sorted_records:
            snippet = r.text.strip().replace("\n", " ")
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            bullet_points.append(f"- [{r.created_at.strftime('%Y-%m-%d')}] {snippet}")

        summary = (
            f"Episodic rollup of {len(records)} memories:\n" +
            "\n".join(bullet_points[:15])
        )

        token_estimate = int(len(summary.split()) * 1.3)
        return {
            "summary": summary,
            "records_compressed": len(records),
            "token_estimate": token_estimate,
        }

    def execute_lifecycle_cycle(
        self,
        facts: List[FactItem],
        records: List[MemoryRecord],
    ) -> Dict[str, Any]:
        """Executes full memory maintenance cycle identifying prune candidates and compressing records."""
        prune_candidates = self.identify_prune_candidates(facts)
        active_facts = [f for f in facts if f not in prune_candidates]

        compression_result = self.compress_episodes(records)

        return {
            "total_facts_evaluated": len(facts),
            "active_facts_retained": len(active_facts),
            "facts_pruned": len(prune_candidates),
            "prune_candidate_ids": [str(f.id) for f in prune_candidates],
            "episodic_compression": compression_result,
        }
