"""Tier 2: Production PostgreSQL Structured Fact Store."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from memory.core.interfaces import BaseFactStore
from memory.core.models import FactItem, FactCategory, utc_now
from memory.core.exceptions import AdapterConnectionError


class PostgreSQLFactStore(BaseFactStore):
    """PostgreSQL structured fact store with schema auto-initialization,
    versioning, and soft decay.
    """

    def __init__(self, connection_url: Optional[str] = None):
        self._url = connection_url
        self._pool = None
        if self._url:
            self._init_db()

    def _get_connection(self):
        if not self._url:
            raise AdapterConnectionError("PostgreSQL connection URL is not configured.")
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(self._url, cursor_factory=RealDictCursor)
        except Exception as e:
            raise AdapterConnectionError(f"Failed to connect to PostgreSQL: {e}")

    def _init_db(self) -> None:
        if not self._url:
            return
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS facts (
                        id UUID PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        key VARCHAR(255) NOT NULL,
                        value TEXT NOT NULL,
                        category VARCHAR(64) NOT NULL,
                        source_event_id UUID,
                        version INTEGER NOT NULL DEFAULT 1,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        confidence_score REAL NOT NULL DEFAULT 1.0,
                        superseded_by UUID,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        last_accessed_at TIMESTAMPTZ NOT NULL,
                        access_count INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS idx_pg_facts_user_active
                    ON facts(user_id, is_active);
                    CREATE INDEX IF NOT EXISTS idx_pg_facts_user_key_active
                    ON facts(user_id, key, is_active);
                """)
                conn.commit()
        finally:
            conn.close()

    def _dict_to_fact(self, row: dict) -> FactItem:
        return FactItem(
            id=row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"])),
            user_id=row["user_id"],
            key=row["key"],
            value=row["value"],
            category=FactCategory(row["category"]),
            source_event_id=row["source_event_id"],
            version=row["version"],
            is_active=row["is_active"],
            confidence_score=float(row["confidence_score"]),
            superseded_by=row["superseded_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            access_count=row["access_count"],
        )

    def put_fact(self, fact: FactItem) -> FactItem:
        conn = self._get_connection()
        now = utc_now()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, version FROM facts WHERE user_id = %s AND key = %s AND is_active = TRUE",
                    (fact.user_id, fact.key),
                )
                existing = cur.fetchone()

                new_version = fact.version
                if existing:
                    old_id = existing["id"]
                    new_version = existing["version"] + 1
                    cur.execute(
                        """
                        UPDATE facts
                        SET is_active = FALSE, superseded_by = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (fact.id, now, old_id),
                    )

                fact.version = new_version
                cur.execute(
                    """
                    INSERT INTO facts (
                        id, user_id, key, value, category, source_event_id,
                        version, is_active, confidence_score, superseded_by,
                        created_at, updated_at, last_accessed_at, access_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        fact.id,
                        fact.user_id,
                        fact.key,
                        fact.value,
                        fact.category.value,
                        fact.source_event_id,
                        fact.version,
                        fact.is_active,
                        fact.confidence_score,
                        fact.superseded_by,
                        fact.created_at,
                        fact.updated_at,
                        fact.last_accessed_at,
                        fact.access_count,
                    ),
                )
                conn.commit()
            return fact
        finally:
            conn.close()

    def get_facts(self, user_id: str, active_only: bool = True) -> List[FactItem]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                q = "SELECT * FROM facts WHERE user_id = %s"
                params = [user_id]
                if active_only:
                    q += " AND is_active = TRUE"
                q += " ORDER BY updated_at DESC"
                cur.execute(q, params)
                return [self._dict_to_fact(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_fact_by_key(self, user_id: str, key: str, active_only: bool = True) -> Optional[FactItem]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                q = "SELECT * FROM facts WHERE user_id = %s AND key = %s"
                params = [user_id, key]
                if active_only:
                    q += " AND is_active = TRUE"
                q += " ORDER BY version DESC LIMIT 1"
                cur.execute(q, params)
                r = cur.fetchone()
                return self._dict_to_fact(r) if r else None
        finally:
            conn.close()

    def invalidate_fact(self, fact_id: UUID, superseded_by: Optional[UUID] = None) -> bool:
        conn = self._get_connection()
        now = utc_now()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE facts
                    SET is_active = FALSE, superseded_by = %s, updated_at = %s
                    WHERE id = %s AND is_active = TRUE
                    """,
                    (superseded_by, now, fact_id),
                )
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    def invalidate_by_key(self, user_id: str, key: str, superseded_by: Optional[UUID] = None) -> int:
        conn = self._get_connection()
        now = utc_now()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE facts
                    SET is_active = FALSE, superseded_by = %s, updated_at = %s
                    WHERE user_id = %s AND key = %s AND is_active = TRUE
                    """,
                    (superseded_by, now, user_id, key),
                )
                conn.commit()
                return cur.rowcount
        finally:
            conn.close()

    def delete_fact(self, fact_id: UUID) -> bool:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM facts WHERE id = %s", (fact_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    def update_fact(self, fact_id: UUID, new_value: str) -> Optional[FactItem]:
        conn = self._get_connection()
        now = utc_now()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE facts
                    SET value = %s, updated_at = %s, version = version + 1
                    WHERE id = %s AND is_active = TRUE
                    """,
                    (new_value, now, fact_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                cur.execute("SELECT * FROM facts WHERE id = %s", (fact_id,))
                r = cur.fetchone()
                return self._dict_to_fact(r) if r else None
        finally:
            conn.close()

    def touch_fact(self, fact_id: UUID) -> None:
        conn = self._get_connection()
        now = utc_now()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE facts
                    SET last_accessed_at = %s, access_count = access_count + 1
                    WHERE id = %s
                    """,
                    (now, fact_id),
                )
                conn.commit()
        finally:
            conn.close()
