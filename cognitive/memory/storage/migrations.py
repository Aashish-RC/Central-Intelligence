"""Schema migration utilities for SQLite fact store.
- add_column_if_missing: helper to add a column if it doesn't exist
"""

import sqlite3
from dataclasses import dataclass
from typing import Callable, List


@dataclass
class Migration:
    """A single schema migration."""
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]


class SchemaMigrator:
    """Applies schema migrations in version order, tracking applied versions."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._ensure_migrations_table()

    def _ensure_migrations_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    def _get_applied_versions(self) -> set:
        try:
            cursor = self._conn.execute("SELECT version FROM _migrations")
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            return set()

    def apply_all(self, migrations: List[Migration]) -> None:
        applied = self._get_applied_versions()
        pending = sorted(
            [m for m in migrations if m.version not in applied],
            key=lambda m: m.version
        )
        for migration in pending:
            migration.up(self._conn)
            self._conn.execute(
                "INSERT INTO _migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name)
            )
            self._conn.commit()


def add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str
) -> None:
    """Add a column to a table if it doesn't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
