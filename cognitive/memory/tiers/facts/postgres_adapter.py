"""Tier 2: Production PostgreSQL Structured Fact Store with Connection Pooling & Concurrency Control."""

from contextlib import contextmanager
from datetime import datetime
import queue
import threading
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


class _PostgreSQLConnectionPool:
    """Thread-safe connection pool for PostgreSQL connections (pg8000 / psycopg2)."""

    def __init__(self, connection_url: str, max_connections: int = 5, timeout: float = 30.0) -> None:
        self._url = connection_url
        self._max_connections = max_connections
        self._timeout = timeout
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._current_size = 0
        self._lock = threading.Lock()
        self._closed = False

    def _create_raw_connection(self) -> Any:
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

    def acquire(self) -> Any:
        if self._closed:
            raise AdapterConnectionError("Connection pool is closed.")

        try:
            return self._pool.get_nowait()
        except queue.Empty:
            pass

        with self._lock:
            if self._current_size < self._max_connections:
                conn = self._create_raw_connection()
                self._current_size += 1
                return conn

        try:
            return self._pool.get(timeout=self._timeout)
        except queue.Empty:
            raise AdapterConnectionError(
                f"Connection pool exhausted (timed out after {self._timeout}s)."
            )

    def release(self, conn: Any) -> None:
        if self._closed:
            try:
                conn.close()
            except Exception:
                pass
            return

        try:
            conn.rollback()
        except Exception:
            pass

        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                self._current_size = max(0, self._current_size - 1)

    def close(self) -> None:
        self._closed = True
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass
        with self._lock:
            self._current_size = 0


class PostgreSQLFactStore(BaseFactStore):
    """PostgreSQL structured fact store with connection pooling, schema auto-initialization,
    row-level concurrency locking (FOR UPDATE), versioning, and soft decay.
    Supports pure-Python pg8000 driver (preferred) and psycopg2 fallback.
    """

    def __init__(self, connection_url: Optional[str] = None, max_pool_size: int = 5):
        self._url = connection_url
        self._max_pool_size = max_pool_size
        self._pool = (
            _PostgreSQLConnectionPool(self._url, max_connections=max_pool_size)
            if self._url
            else None
        )
        if self._url:
            self._init_db()

    @contextmanager
    def _connection(self):
        if not self._pool:
            raise AdapterConnectionError("PostgreSQL connection URL is not configured.")
        conn = self._pool.acquire()
        try:
            yield conn
        finally:
            self._pool.release(conn)

    def _get_connection(self):
        if not self._pool:
            raise AdapterConnectionError("PostgreSQL connection URL is not configured.")
        return self._pool.acquire()

    def close(self) -> None:
        """Close connection pool and release resources."""
        if self._pool:
            self._pool.close()

    def _init_db(self) -> None:
        if not self._url:
            return
        with self._connection() as conn:
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
        with self._connection() as conn:
            now = utc_now()
            with conn.cursor() as cur:
                # Concurrency control: Lock active fact row for update during mutation
                cur.execute(
                    "SELECT id, version FROM facts WHERE user_id = %s AND key = %s AND is_active = TRUE FOR UPDATE",
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

    def get_facts(self, user_id: str, active_only: bool = True) -> List[FactItem]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                q = "SELECT * FROM facts WHERE user_id = %s"
                params = [user_id]
                if active_only:
                    q += " AND is_active = TRUE"
                q += " ORDER BY updated_at DESC"
                cur.execute(q, params)
                return [self._dict_to_fact(r) for r in cur.fetchall()]

    def get_fact_by_key(self, user_id: str, key: str, active_only: bool = True) -> Optional[FactItem]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                q = "SELECT * FROM facts WHERE user_id = %s AND key = %s"
                params = [user_id, key]
                if active_only:
                    q += " AND is_active = TRUE"
                q += " ORDER BY version DESC LIMIT 1"
                cur.execute(q, params)
                r = cur.fetchone()
                return self._dict_to_fact(r) if r else None

    def invalidate_fact(self, fact_id: UUID, superseded_by: Optional[UUID] = None) -> bool:
        with self._connection() as conn:
            now = utc_now()
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

    def invalidate_by_key(self, user_id: str, key: str, superseded_by: Optional[UUID] = None) -> int:
        with self._connection() as conn:
            now = utc_now()
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

    def delete_fact(self, fact_id: UUID) -> bool:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM facts WHERE id = %s", (fact_id,))
                conn.commit()
                return cur.rowcount > 0

    def update_fact(self, fact_id: UUID, new_value: str) -> Optional[FactItem]:
        with self._connection() as conn:
            now = utc_now()
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

    def touch_fact(self, fact_id: UUID) -> None:
        with self._connection() as conn:
            now = utc_now()
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
