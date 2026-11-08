"""Tier 2: Fact Store (SQLite / PostgreSQL Entity & Constraint Repository)."""

import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4


class FactStoreTier:
    """Persistent SQLite-backed key-entity fact and constraint store."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", str(Path.home() / ".pheonix" / "agent_facts.db"))
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite facts table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    fact_text TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    created_at REAL NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_ns ON facts(namespace)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(namespace, entity_key)")
            conn.commit()

    def save_fact(
        self,
        namespace: str,
        entity_key: str,
        fact_text: str,
        category: str = "general",
        confidence: float = 1.0,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Store or update a verified fact."""
        fact_id = str(uuid4())
        meta_str = json.dumps(metadata or {})
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO facts (id, namespace, entity_key, fact_text, category, confidence, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (fact_id, namespace, entity_key, fact_text, category, confidence, now, meta_str))
            conn.commit()

        return fact_id

    def query_facts(
        self,
        namespace: str,
        entity_key: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve facts matching namespace and filters."""
        query = "SELECT id, namespace, entity_key, fact_text, category, confidence, created_at, metadata_json FROM facts WHERE namespace = ?"
        params: List[Any] = [namespace]

        if entity_key:
            query += " AND entity_key = ?"
            params.append(entity_key)

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "namespace": row[1],
                    "entity_key": row[2],
                    "fact_text": row[3],
                    "category": row[4],
                    "confidence": row[5],
                    "created_at": row[6],
                    "metadata": json.loads(row[7]),
                })

        return results

    def delete_facts(self, namespace: str, entity_key: Optional[str] = None) -> int:
        """Delete facts under a namespace."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if entity_key:
                cursor.execute("DELETE FROM facts WHERE namespace = ? AND entity_key = ?", (namespace, entity_key))
            else:
                cursor.execute("DELETE FROM facts WHERE namespace = ?", (namespace,))
            conn.commit()
            return cursor.rowcount
