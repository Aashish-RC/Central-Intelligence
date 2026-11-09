"""Snapshot Manager for Rollback of Learned Adaptations (Feature 2.51)."""

import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4
from memory.snapshots.models import (
    FactSnapshotItem,
    LessonSnapshotItem,
    MemorySnapshot,
    RollbackResult,
)


class MemorySnapshotManager:
    """Manages versioned point-in-time snapshots of memory facts and learned lessons."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or ":memory:"
        self._memory_cache: Dict[str, MemorySnapshot] = {}
        self._init_db()

    def _init_db(self) -> None:
        if self._db_path == ":memory:":
            return

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_snapshots (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
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
        user_id: str,
        engine: Any,
        tag: Optional[str] = None,
        description: Optional[str] = None,
    ) -> MemorySnapshot:
        """Captures a complete point-in-time snapshot of user facts, lessons, and state."""
        snap_id = f"snap_{uuid4().hex[:12]}"

        # 1. Capture facts
        facts_list: List[FactSnapshotItem] = []
        if hasattr(engine, "facts") and engine.facts is not None:
            raw_facts = []
            if hasattr(engine.facts, "get_facts"):
                raw_facts = engine.facts.get_facts(user_id=user_id)
            elif hasattr(engine.facts, "list_facts"):
                raw_facts = engine.facts.list_facts(user_id=user_id)

            for f in raw_facts:
                facts_list.append(
                    FactSnapshotItem(
                        id=str(getattr(f, "id", "")),
                        key=f.key,
                        value=f.value,
                        category=getattr(f.category, "value", str(f.category)),
                        confidence_score=getattr(f, "confidence_score", getattr(f, "confidence", 1.0)),
                        context=getattr(f, "context", None),
                    )
                )

        # 2. Capture lessons
        lessons_list: List[LessonSnapshotItem] = []
        if hasattr(engine, "lesson_store") and engine.lesson_store is not None:
            raw_lessons = engine.lesson_store.query_lessons(query="", limit=100)
            for l in raw_lessons:
                lessons_list.append(
                    LessonSnapshotItem(
                        lesson_id=l.lesson_id,
                        title=l.title,
                        category=getattr(l.category, "value", str(l.category)),
                        trigger_context=l.trigger_context,
                        mistake=l.mistake,
                        resolution=l.resolution,
                        rule=l.rule,
                        confidence=l.confidence,
                    )
                )

        snapshot = MemorySnapshot(
            id=snap_id,
            user_id=user_id,
            tag=tag,
            description=description,
            facts=facts_list,
            lessons=lessons_list,
        )

        self._memory_cache[snap_id] = snapshot

        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO memory_snapshots (id, user_id, tag, description, created_at, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (snap_id, user_id, tag, description, snapshot.created_at, snapshot.model_dump_json()),
                )
                conn.commit()

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[MemorySnapshot]:
        """Retrieves a snapshot by ID."""
        if snapshot_id in self._memory_cache:
            return self._memory_cache[snapshot_id]

        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "SELECT payload_json FROM memory_snapshots WHERE id = ?",
                    (snapshot_id,),
                )
                row = cursor.fetchone()
                if row:
                    snap = MemorySnapshot.model_validate_json(row[0])
                    self._memory_cache[snapshot_id] = snap
                    return snap

        return None

    def list_snapshots(self, user_id: str) -> List[MemorySnapshot]:
        """Lists all snapshots captured for a user."""
        res: List[MemorySnapshot] = [
            s for s in self._memory_cache.values() if s.user_id == user_id
        ]
        if self._db_path != ":memory:":
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "SELECT payload_json FROM memory_snapshots WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
                for row in cursor.fetchall():
                    snap = MemorySnapshot.model_validate_json(row[0])
                    if snap.id not in [s.id for s in res]:
                        res.append(snap)
        return res

    def rollback(
        self,
        user_id: str,
        snapshot_id: str,
        engine: Any,
    ) -> RollbackResult:
        """Rolls back the live memory engine to the state captured in the snapshot."""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                user_id=user_id,
                message=f"Snapshot {snapshot_id} not found.",
            )

        if snapshot.user_id != user_id:
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                user_id=user_id,
                message=f"Access denied: snapshot {snapshot_id} belongs to another user.",
            )

        facts_restored = 0
        facts_removed = 0
        lessons_restored = 0
        lessons_removed = 0

        # 1. Rollback facts
        if hasattr(engine, "facts") and engine.facts is not None:
            # Query current active facts
            current_facts = (
                engine.facts.get_facts(user_id=user_id)
                if hasattr(engine.facts, "get_facts")
                else []
            )
            snapshot_fact_keys = {
                (f.key, f.value) for f in snapshot.facts
            }

            # Invalidate facts that were added after snapshot
            for cf in current_facts:
                if (cf.key, cf.value) not in snapshot_fact_keys:
                    if hasattr(engine.facts, "invalidate_fact"):
                        engine.facts.invalidate_fact(cf.id)
                    elif hasattr(engine.facts, "delete_fact"):
                        engine.facts.delete_fact(cf.id)
                    facts_removed += 1

            # Restore facts present in snapshot
            for sf in snapshot.facts:
                from memory.core.models import FactItem, FactCategory
                cat = FactCategory(sf.category) if sf.category in FactCategory._value2member_map_ else FactCategory.FACT
                item = FactItem(
                    user_id=user_id,
                    key=sf.key,
                    value=sf.value,
                    category=cat,
                    confidence_score=sf.confidence_score,
                )
                if hasattr(engine.facts, "put_fact"):
                    engine.facts.put_fact(item)
                elif hasattr(engine.facts, "save_fact"):
                    engine.facts.save_fact(item)
                facts_restored += 1

        # 2. Rollback lessons
        if hasattr(engine, "lesson_store") and engine.lesson_store is not None:
            # Delete current lessons and reinstate snapshot lessons
            current_lessons = engine.lesson_store.query_lessons(query="", limit=100)
            snapshot_lesson_ids = {l.lesson_id for l in snapshot.lessons}

            for cl in current_lessons:
                if cl.lesson_id not in snapshot_lesson_ids:
                    engine.lesson_store.delete_lesson(cl.lesson_id)
                    lessons_removed += 1

            for sl in snapshot.lessons:
                from memory.lessons.models import LessonRecord, LessonCategory
                cat = LessonCategory(sl.category) if sl.category in LessonCategory._value2member_map_ else LessonCategory.GENERAL
                record = LessonRecord(
                    lesson_id=sl.lesson_id,
                    title=sl.title,
                    category=cat,
                    trigger_context=sl.trigger_context,
                    mistake=sl.mistake,
                    resolution=sl.resolution,
                    rule=sl.rule,
                    confidence=sl.confidence,
                )
                engine.lesson_store.save_lesson(record)
                lessons_restored += 1

        return RollbackResult(
            success=True,
            snapshot_id=snapshot_id,
            user_id=user_id,
            facts_restored=facts_restored,
            facts_removed=facts_removed,
            lessons_restored=lessons_restored,
            lessons_removed=lessons_removed,
            message=f"Successfully rolled back to snapshot {snapshot_id} ({snapshot.tag or 'untagged'}).",
        )
