"""Memory Sources View Builder for inspecting provenance, source events, and confidence."""

from typing import List
from memory.core.models import (
    FactItem,
    MemoryRecord,
    MemorySourceItem,
    MemorySourcesView,
    SourceProvenance,
)


class MemorySourcesViewBuilder:
    """Constructs a unified, transparent view of active and historical memory sources
    enabling provenance inspection and granular deletion.
    """

    @staticmethod
    def build(
        user_id: str,
        project_id: str,
        facts: List[FactItem],
        archival_records: List[MemoryRecord],
    ) -> MemorySourcesView:
        items: List[MemorySourceItem] = []

        for f in facts:
            source_type = "user_turn" if f.source_event_id else "inferred_fact"
            provenance = SourceProvenance(
                source_type=source_type,
                confidence=f.confidence_score,
                source_ref=str(f.source_event_id) if f.source_event_id else None,
                extracted_at=f.created_at,
            )
            items.append(
                MemorySourceItem(
                    item_id=str(f.id),
                    item_type="fact",
                    project_id=f.project_id or project_id,
                    user_id=f.user_id,
                    summary_text=f"{f.key}: {f.value}",
                    provenance=provenance,
                    created_at=f.created_at,
                    is_active=f.is_active,
                )
            )

        for m in archival_records:
            provenance = SourceProvenance(
                source_type="archival_vector",
                confidence=m.confidence_score,
                source_ref=m.session_id,
                extracted_at=m.created_at,
            )
            items.append(
                MemorySourceItem(
                    item_id=str(m.id),
                    item_type="archival",
                    project_id=m.project_id or project_id,
                    user_id=m.user_id,
                    summary_text=m.text,
                    provenance=provenance,
                    created_at=m.created_at,
                    is_active=m.is_active,
                )
            )

        return MemorySourcesView(
            project_id=project_id,
            user_id=user_id,
            total_sources=len(items),
            facts_count=len(facts),
            archival_count=len(archival_records),
            items=items,
        )
