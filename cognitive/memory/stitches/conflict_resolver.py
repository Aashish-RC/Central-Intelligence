"""Stitch 3: Deduplication and Contradiction Resolution."""

from typing import List, Optional
from memory.core.models import FactItem
from memory.core.interfaces import BaseFactStore


class ConflictResolver:
    """Detects duplicates and semantic contradictions across incoming facts and historical state,
    ensuring old or contradictory memories are gracefully superseded.
    """

    def __init__(self, fact_store: BaseFactStore):
        self._fact_store = fact_store

    def resolve_and_apply(
        self,
        candidate_facts: List[FactItem],
        keys_to_invalidate: Optional[List[str]] = None,
    ) -> List[FactItem]:
        """Resolves contradictions and applies mutations against the underlying fact store.
        
        Returns the list of final stored active facts.
        """
        keys_to_invalidate = set(keys_to_invalidate or [])
        applied_facts: List[FactItem] = []
        handled_keys = set()

        # Check each candidate against active facts
        for candidate in candidate_facts:
            handled_keys.add(candidate.key)
            existing = self._fact_store.get_fact_by_key(
                user_id=candidate.user_id,
                key=candidate.key,
                active_only=True,
            )

            if existing:
                # Deduplication: identical key & value
                if existing.value.strip().lower() == candidate.value.strip().lower():
                    self._fact_store.touch_fact(existing.id)
                    applied_facts.append(existing)
                    continue

                # Contradiction: same key, different value -> increment version and supersede
                candidate.version = max(candidate.version, existing.version + 1)
                self._fact_store.invalidate_fact(existing.id, superseded_by=candidate.id)

            saved = self._fact_store.put_fact(candidate)
            applied_facts.append(saved)

        # Invalidate any remaining keys explicitly requested that weren't in candidate_facts
        remaining_keys = keys_to_invalidate - handled_keys
        if candidate_facts:
            target_user = candidate_facts[0].user_id
            for key in remaining_keys:
                self._fact_store.invalidate_by_key(target_user, key)

        return applied_facts
