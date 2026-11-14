"""Tier 2: Production PostgreSQL Structured Fact Store."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import urllib.parse
from uuid import UUID

from cognitive.memory.core.interfaces import BaseFactStore
from cognitive.memory.core.models import FactItem, FactCategory, utc_now
from cognitive.memory.core.exceptions import AdapterConnectionError


class _Pg8000DictCursor:
    """Wrapper around a pg8000 DB-API cursor providing dictionary-like row access."""

    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, operation: str, parameters: Any = None) -> Any:
        return self._cursor.execute(operation, parameters)

    def executemany(self, operation: str, seq_of_parameters: Any) -> Any:
        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self) -> Optional[Dict[str, Any]]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        col_names = [d[0] for d in self._cursor.description]
        return dict(zip(col_names, row))

    def fetchall(self) -> List[Dict[str, Any]]:
        rows = self._cursor.fetchall()
        if not rows:
            return []
        col_names = [d[0] for d in self._cursor.description]
        return [dict(zip(col_names, r)) for r in rows]

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def close(self) -> None:
        self._cursor.close()

    def __enter__(self) -> "_Pg8000DictCursor":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cursor.close()


class _Pg8000ConnectionWrapper:
    """Wrapper around a pg8000 DB-API connection providing RealDictCursor semantics."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def cursor(self) -> _Pg8000DictCursor:
        return _Pg8000DictCursor(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


class PostgreSQLFactStore(BaseFactStore):
    """PostgreSQL structured fact store with schema auto-initialization,
    versioning, and soft decay.
    Supports pure-Python pg8000 driver (preferred) and psycopg2 fallback.
    """

    def __init__(self, connection_url: Optional[str] = None):
        self._url = connection_url
        self._pool = None
        if self._url:
            self._init_db()

    def _get_connection(self):
        if not self._url:
            raise AdapterConnectionError("PostgreSQL connection URL is not configured.")

        # 1. Prefer pg8000 (locked in requirements.lock, pure-Python)
        pg8000_err = None
        try:
            import pg8000.dbapi

            parsed = urllib.parse.urlparse(self._url)
            conn = pg8000.dbapi.connect(
                user=parsed.username or "postgres",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip("/") or "postgres",
            )
            return _Pg8000ConnectionWrapper(conn)
        except ImportError:
            pass
        except Exception as exc:
            pg8000_err = exc

        # 2. Fall back to psycopg2 if available
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            return psycopg2.connect(self._url, cursor_factory=RealDictCursor)
        except ImportError:
            pass
        except Exception as exc:
            raise AdapterConnectionError(f"Failed to connect to PostgreSQL via psycopg2: {exc}") from exc

        if pg8000_err is not None:
            raise AdapterConnectionError(f"Failed to connect to PostgreSQL via pg8000: {pg8000_err}") from pg8000_err

        raise AdapterConnectionError(
            "Neither 'pg8000' nor 'psycopg2' is available to connect to PostgreSQL. "
            "Please ensure pg8000 (specified in pyproject.toml) is installed."
        )

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
        raw_source = row.get("source_event_id")
        source_id = None
        if raw_source is not None:
            source_id = raw_source if isinstance(raw_source, UUID) else UUID(str(raw_source))

        raw_superseded = row.get("superseded_by")
        superseded_id = None
        if raw_superseded is not None:
            superseded_id = raw_superseded if isinstance(raw_superseded, UUID) else UUID(str(raw_superseded))

        return FactItem(
            id=row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"])),
            user_id=row["user_id"],
            key=row["key"],
            value=row["value"],
            category=FactCategory(row["category"]),
            source_event_id=source_id,
            version=row["version"],
            is_active=row["is_active"],
            confidence_score=float(row["confidence_score"]),
            superseded_by=superseded_id,
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
