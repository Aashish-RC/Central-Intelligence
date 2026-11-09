"""Storage repository for Lessons Learned.

Provides indexing and querying for procedural lessons to inject into agent
reasoning loops.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
from .models import LessonCategory, LessonRecord


class LessonStore:
    """Manages persistence and retrieval of distilled lessons learned."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._memory_cache: Dict[str, LessonRecord] = {}

        if self.db_path and self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons_learned (
                    lesson_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    trigger_context TEXT NOT NULL,
                    mistake TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    rule TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    application_count INTEGER DEFAULT 0,
                    source_session_id TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def save_lesson(self, lesson: LessonRecord) -> None:
        """Persist or update a lesson record."""
        self._memory_cache[lesson.lesson_id] = lesson

        if self.db_path and self.db_path != ":memory:":
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO lessons_learned (
                        lesson_id, title, category, trigger_context, mistake,
                        resolution, rule, confidence, application_count,
                        source_session_id, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    lesson.lesson_id,
                    lesson.title,
                    lesson.category.value,
                    lesson.trigger_context,
                    lesson.mistake,
                    lesson.resolution,
                    lesson.rule,
                    lesson.confidence,
                    lesson.application_count,
                    lesson.source_session_id,
                    json.dumps(lesson.metadata),
                    lesson.created_at.isoformat(),
                    lesson.updated_at.isoformat(),
                ))
                conn.commit()

    def get_lesson(self, lesson_id: str) -> Optional[LessonRecord]:
        """Fetch lesson by unique ID."""
        if lesson_id in self._memory_cache:
            return self._memory_cache[lesson_id]

        if self.db_path and self.db_path != ":memory:":
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM lessons_learned WHERE lesson_id = ?", (lesson_id,)
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_record(row)
        return None

    def query_lessons(
        self,
        query: str,
        category: Optional[LessonCategory] = None,
        limit: int = 5,
    ) -> List[LessonRecord]:
        """Rank and return lessons relevant to a task query or command."""
        query_words = set(query.lower().split())
        candidates: List[LessonRecord] = list(self._memory_cache.values())

        if self.db_path and self.db_path != ":memory:" and not candidates:
            candidates = self.list_all()

        scored: List[tuple[float, LessonRecord]] = []
        for l in candidates:
            if category and l.category != category:
                continue

            score = 0.0
            trigger_words = set(l.trigger_context.lower().split())
            title_words = set(l.title.lower().split())
            rule_words = set(l.rule.lower().split())

            # Keyword overlap scoring
            overlap = query_words.intersection(trigger_words)
            score += len(overlap) * 3.0

            title_overlap = query_words.intersection(title_words)
            score += len(title_overlap) * 2.0

            rule_overlap = query_words.intersection(rule_words)
            score += len(rule_overlap) * 1.0

            score *= l.confidence

            if score > 0 or not query_words:
                scored.append((score, l))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def record_application(self, lesson_id: str) -> None:
        """Increment application counter when a lesson is referenced or applied."""
        lesson = self.get_lesson(lesson_id)
        if lesson:
            lesson.application_count += 1
            lesson.updated_at = datetime.now(timezone.utc)
            self.save_lesson(lesson)

    def list_all(self) -> List[LessonRecord]:
        """Return all stored lessons."""
        if self._memory_cache:
            return list(self._memory_cache.values())

        if self.db_path and self.db_path != ":memory:":
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM lessons_learned ORDER BY created_at DESC")
                return [self._row_to_record(r) for r in cursor.fetchall()]
        return []

    def clear(self) -> None:
        """Clear all stored lessons."""
        self._memory_cache.clear()
        if self.db_path and self.db_path != ":memory:":
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM lessons_learned")
                conn.commit()

    def _row_to_record(self, row: tuple) -> LessonRecord:
        return LessonRecord(
            lesson_id=row[0],
            title=row[1],
            category=LessonCategory(row[2]),
            trigger_context=row[3],
            mistake=row[4],
            resolution=row[5],
            rule=row[6],
            confidence=float(row[7]),
            application_count=int(row[8]),
            source_session_id=row[9],
            metadata=json.loads(row[10]) if row[10] else {},
            created_at=datetime.fromisoformat(row[11]),
            updated_at=datetime.fromisoformat(row[12]),
        )
