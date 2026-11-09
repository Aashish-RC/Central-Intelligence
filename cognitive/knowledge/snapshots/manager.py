"""Point-in-Time Knowledge Snapshot Manager (Feature 3.24)."""

import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4
from knowledge.snapshots.models import (
    GraphRelationshipSnapshot,
    KnowledgeItemSnapshot,
    KnowledgeSnapshot,
    SnapshotDiffResult,
)


class KnowledgeSnapshotManager:
    """Manages immutable point-in-time snapshots of knowledge documents and graph triples."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or ":memory:"
        self._cache: Dict[str, KnowledgeSnapshot] = {}
        self._init_db()

    def _init_db(self) -> None:
        if self._db_path == ":memory:":
            return

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_snapshots (
                    id TEXT PRIMARY KEY,
                    tag TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_snapshot(
        self,
        items: List[KnowledgeItemSnapshot],
        relationships: Optional[List[GraphRelationshipSnapshot]] = None,
        tag: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeSnapshot:
        """Captures an immutable snapshot of current knowledge items and graph relationships."""
        snap_id = f"ksnap_{uuid4().hex[:12]}"
        rels = relationships or []

        snapshot = KnowledgeSnapshot(
            snapshot_id=snap_id,
            tag=tag,
            description=description,
            items=items,
            relationships=rels,
            total_items=len(items),
            total_relationships=len(rels),
            metadata=metadata or {},
        )

        self._cache[snap_id] = snapshot

        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO knowledge_snapshots (id, tag, description, created_at, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (snap_id, tag, description, snapshot.created_at, snapshot.model_dump_json()),
                )
                conn.commit()

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[KnowledgeSnapshot]:
        """Retrieves snapshot by ID."""
        if snapshot_id in self._cache:
            return self._cache[snapshot_id]

        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "SELECT payload_json FROM knowledge_snapshots WHERE id = ?",
                    (snapshot_id,),
                )
                row = cursor.fetchone()
                if row:
                    snap = KnowledgeSnapshot.model_validate_json(row[0])
                    self._cache[snapshot_id] = snap
                    return snap

        return None

    def list_snapshots(self) -> List[KnowledgeSnapshot]:
        """Lists all snapshots."""
        res = list(self._cache.values())
        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("SELECT payload_json FROM knowledge_snapshots ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    snap = KnowledgeSnapshot.model_validate_json(row[0])
                    if snap.snapshot_id not in [s.snapshot_id for s in res]:
                        res.append(snap)
        return res

    def diff_snapshots(self, base_id: str, target_id: str) -> SnapshotDiffResult:
        """Computes structural diff between two point-in-time snapshots."""
        base = self.get_snapshot(base_id)
        target = self.get_snapshot(target_id)

        if not base or not target:
            raise ValueError(f"Snapshot not found (base={base_id}, target={target_id})")

        base_items_map = {item.id: item for item in base.items}
        target_items_map = {item.id: item for item in target.items}

        added_items = [target_items_map[i] for i in target_items_map if i not in base_items_map]
        removed_items = [base_items_map[i] for i in base_items_map if i not in target_items_map]
        modified_items = []

        for item_id in base_items_map:
            if item_id in target_items_map:
                b_item = base_items_map[item_id]
                t_item = target_items_map[item_id]
                if b_item.content != t_item.content or b_item.version != t_item.version:
                    modified_items.append({
                        "id": item_id,
                        "title": t_item.title,
                        "old_version": b_item.version,
                        "new_version": t_item.version,
                    })

        # Relationship diff
        base_rels = {(r.source, r.relation, r.target): r for r in base.relationships}
        target_rels = {(r.source, r.relation, r.target): r for r in target.relationships}

        added_rels = [target_rels[k] for k in target_rels if k not in base_rels]
        removed_rels = [base_rels[k] for k in base_rels if k not in target_rels]

        return SnapshotDiffResult(
            base_snapshot_id=base_id,
            target_snapshot_id=target_id,
            added_items=added_items,
            removed_items=removed_items,
            modified_items=modified_items,
            added_relationships=added_rels,
            removed_relationships=removed_rels,
        )

    def query_point_in_time(
        self,
        snapshot_id: str,
        query: str,
    ) -> List[KnowledgeItemSnapshot]:
        """Queries knowledge items as of a specific historical snapshot."""
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            return []

        lower_q = query.lower()
        matched: List[KnowledgeItemSnapshot] = []

        for item in snap.items:
            if (
                lower_q in item.title.lower()
                or lower_q in item.content.lower()
                or any(lower_q in t.lower() for t in item.tags)
            ):
                matched.append(item)

        return matched
