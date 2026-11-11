"""Source Version Tracking & Incremental Diff Re-Ingestion (L3 Feature 3.17).

Hashes source content blocks, detects added/modified/removed sections on
subsequent versions, and re-indexes strictly the changed diff blocks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk


@dataclass
class DiffSummary:
    """Result of incremental source version comparison & re-ingestion."""

    source_id: str
    version_number: int
    unchanged_blocks: int
    added_or_updated_blocks: int
    removed_blocks: int
    reingested_chunk_ids: List[str] = field(default_factory=list)


class SourceVersionTracker:
    """Tracks per-block content digests so unchanged content is never re-ingested."""

    def __init__(self, index: Optional[InMemoryKnowledgeIndex] = None) -> None:
        self.index = index or InMemoryKnowledgeIndex()
        self._versions: Dict[str, int] = {}
        # source_id -> {block_idx: (sha256, chunk_id)}
        self._block_hashes: Dict[str, Dict[int, tuple[str, str]]] = {}

    @staticmethod
    def split_blocks(content: str) -> List[str]:
        blocks = [b.strip() for b in content.replace("\r\n", "\n").split("\n\n") if b.strip()]
        if not blocks and content.strip():
            blocks = [content.strip()]
        return blocks

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def sync_source(self, source_id: str, content: str, modality: str = "web") -> DiffSummary:
        """Compare `content` against prior version and update only changed blocks."""
        blocks = self.split_blocks(content)
        prev = self._block_hashes.get(source_id, {})
        next_ver = self._versions.get(source_id, 0) + 1

        unchanged = 0
        updated_ids: List[str] = []
        new_map: Dict[int, tuple[str, str]] = {}

        for idx, block_text in enumerate(blocks):
            h = self._digest(block_text)
            cid = f"{source_id}:blk:{idx}"
            if idx in prev and prev[idx][0] == h:
                unchanged += 1
                new_map[idx] = prev[idx]
            else:
                self.index.add(
                    KnowledgeChunk(
                        chunk_id=cid,
                        source_id=source_id,
                        modality=modality,
                        text=block_text,
                        metadata={"version": next_ver, "block_index": idx, "sha256": h[:16]},
                    )
                )
                updated_ids.append(cid)
                new_map[idx] = (h, cid)

        removed_cids = [cid for idx, (_h, cid) in prev.items() if idx >= len(blocks)]
        if removed_cids:
            self.index.delete_chunks(removed_cids)

        if updated_ids or removed_cids or source_id not in self._versions:
            self._versions[source_id] = next_ver
        else:
            next_ver = self._versions[source_id]

        self._block_hashes[source_id] = new_map
        return DiffSummary(
            source_id=source_id,
            version_number=next_ver,
            unchanged_blocks=unchanged,
            added_or_updated_blocks=len(updated_ids),
            removed_blocks=len(removed_cids),
            reingested_chunk_ids=updated_ids,
        )

