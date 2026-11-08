"""Tier 2: Local SQLite Structured Fact Store with automatic migrations and versioning."""

from datetime import datetime
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional
from uuid import UUID

from memory.core.interfaces import BaseFactStore
from memory.core.models import FactItem, FactCategory, utc_now


class SQLiteFactStore(BaseFactStore):
    """Local SQLite structured fact store with schema auto-migrations, version tracking,
    and soft decay metrics.
    """

    def __init__(self, db_path: str = "./facts.db"):
        self._db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_event_id TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    confidence_score REAL NOT NULL DEFAULT 1.0,
                    superseded_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0
                );
            """)

            def _migrate_v1_legacy(c: sqlite3.Connection):
                add_column_if_missing(c, "facts", "project_id", "TEXT DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_user_active
                    ON facts(user_id, is_active);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_user_key_active
                    ON facts(user_id, key, is_active);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_project
                    ON facts(project_id);
                """)

            def _migrate_v2_tenant(c: sqlite3.Connection):
                add_column_if_missing(c, "facts", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_tenant
                    ON facts(tenant_id);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_facts_tenant_user_active
                    ON facts(tenant_id, user_id, is_active);
                """)

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="facts_initial_and_project_id", up=_migrate_v1_legacy),
                Migration(version=2, name="facts_tenant_id", up=_migrate_v2_tenant),
            ])

            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _row_to_fact(self, row: sqlite3.Row) -> FactItem:
        cols = row.keys()
        return FactItem(
            id=UUID(row["id"]),
            tenant_id=row["tenant_id"] if "tenant_id" in cols and row["tenant_id"] else "default",
            user_id=row["user_id"],
            project_id=row["project_id"] if "project_id" in cols and row["project_id"] else "default",
            key=row["key"],
            value=row["value"],
            category=FactCategory(row["category"]),
            source_event_id=UUID(row["source_event_id"]) if row["source_event_id"] else None,
            version=row["version"],
            is_active=bool(row["is_active"]),
            confidence_score=float(row["confidence_score"]),
            superseded_by=UUID(row["superseded_by"]) if row["superseded_by"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
            access_count=row["access_count"],
        )

    def put_fact(self, fact: FactItem) -> FactItem:
        """Insert or update a fact. If an active fact with the same key exists,
        increment version and mark prior record as superseded.
        """
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                # Check for existing latest fact for this user, tenant, project, and key
                cur = conn.execute(
                    "SELECT id, version FROM facts WHERE user_id = ? AND tenant_id = ? AND project_id = ? AND key = ? AND is_active = 1",
                    (fact.user_id, fact.tenant_id or "default", fact.project_id or "default", fact.key),
                )
                existing = cur.fetchone()

                new_version = fact.version
                if existing:
                    old_id = existing["id"]
                    new_version = max(fact.version, existing["version"] + 1)
                    # Invalidate previous record
                    conn.execute(
                        """
                        UPDATE facts
                        SET is_active = 0, superseded_by = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (str(fact.id), now, old_id),
                    )

                fact.version = new_version
                conn.execute(
                    """
                    INSERT INTO facts (
                        id, tenant_id, user_id, project_id, key, value, category, source_event_id,
                        version, is_active, confidence_score, superseded_by,
                        created_at, updated_at, last_accessed_at, access_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(fact.id),
                        fact.tenant_id or "default",
                        fact.user_id,
                        fact.project_id or "default",
                        fact.key,
                        fact.value,
                        fact.category.value,
                        str(fact.source_event_id) if fact.source_event_id else None,
                        fact.version,
                        1 if fact.is_active else 0,
                        fact.confidence_score,
                        str(fact.superseded_by) if fact.superseded_by else None,
                        fact.created_at.isoformat(),
                        fact.updated_at.isoformat(),
                        fact.last_accessed_at.isoformat(),
                        fact.access_count,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
        return fact

    def get_facts(
        self,
        user_id: str,
        active_only: bool = True,
        project_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[FactItem]:
        query = "SELECT * FROM facts WHERE user_id = ?"
        params: list = [user_id]
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if active_only:
            query += " AND is_active = 1"
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC"

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query, params)
                return [self._row_to_fact(row) for row in cur.fetchall()]
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_fact_by_key(
        self,
        user_id: str,
        key: str,
        active_only: bool = True,
        project_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[FactItem]:
        query = "SELECT * FROM facts WHERE user_id = ? AND key = ?"
        params: list = [user_id, key]
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if active_only:
            query += " AND is_active = 1"
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY version DESC LIMIT 1"

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query, params)
                row = cur.fetchone()
                return self._row_to_fact(row) if row else None
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_fact(self, fact_id: UUID) -> bool:
        """Permanently delete a fact from storage."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute("DELETE FROM facts WHERE id = ?", (str(fact_id),))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_fact(self, fact_id: UUID, new_value: str) -> Optional[FactItem]:
        """Directly update the value of an existing active fact."""
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """
                    UPDATE facts
                    SET value = ?, updated_at = ?, version = version + 1
                    WHERE id = ? AND is_active = 1
                    """,
                    (new_value, now, str(fact_id)),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                cur = conn.execute("SELECT * FROM facts WHERE id = ?", (str(fact_id),))
                row = cur.fetchone()
                return self._row_to_fact(row) if row else None
            finally:
                if self._memory_conn is None:
                    conn.close()

    def invalidate_fact(self, fact_id: UUID, superseded_by: Optional[UUID] = None) -> bool:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """
                    UPDATE facts
                    SET is_active = 0, superseded_by = ?, updated_at = ?
                    WHERE id = ? AND is_active = 1
                    """,
                    (str(superseded_by) if superseded_by else None, now, str(fact_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def invalidate_by_key(self, user_id: str, key: str, superseded_by: Optional[UUID] = None) -> int:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """
                    UPDATE facts
                    SET is_active = 0, superseded_by = ?, updated_at = ?
                    WHERE user_id = ? AND key = ? AND is_active = 1
                    """,
                    (str(superseded_by) if superseded_by else None, now, user_id, key),
                )
                conn.commit()
                return cur.rowcount
            finally:
                if self._memory_conn is None:
                    conn.close()

    def touch_fact(self, fact_id: UUID) -> None:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE facts
                    SET last_accessed_at = ?, access_count = access_count + 1
                    WHERE id = ?
                    """,
                    (now, str(fact_id)),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
