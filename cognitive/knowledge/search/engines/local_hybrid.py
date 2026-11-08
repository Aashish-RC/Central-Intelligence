"""Local Embedded Hybrid Search Engine: SQLite FTS5 BM25 + Vector Cosine Indexing with RRF."""

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..core.interfaces import BaseSearchEngine
from ..core.models import (
    CorpusType,
    SearchDocument,
    SearchQuery,
    SearchResponse,
    SearchResult,
    utc_now,
)
from .rrf import ReciprocalRankFusion


class LocalHybridSearchEngine(BaseSearchEngine):
    """Zero-dependency local hybrid search engine combining SQLite FTS5 full-text
    indexing with cosine vector ranking and Reciprocal Rank Fusion.
    """

    def __init__(self, db_path: str = "./search.db", dim: int = 128):
        self._db_path = db_path
        self._dim = dim
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row

        self._lock = threading.Lock()
        self._rrf = ReciprocalRankFusion()
        # In-memory document & vector registry for fast cosine calculation
        self._vectors: Dict[str, np.ndarray] = {}
        self._docs: Dict[str, SearchDocument] = {}

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._lock:
            conn = self._get_connection()
            # Metadata store table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_docs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    corpus_type TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding_json TEXT,
                    timestamp TEXT NOT NULL
                );
            """)

            def _migrate_v1_tables_and_indexes(c: sqlite3.Connection):
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_project
                    ON search_docs(project_id);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_project_corpus
                    ON search_docs(project_id, corpus_type);
                """)
                c.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                        id UNINDEXED,
                        project_id UNINDEXED,
                        corpus_type UNINDEXED,
                        title,
                        content,
                        tags,
                        tokenize = 'porter unicode61'
                    );
                """)

            def _migrate_v2_tenant_id(c: sqlite3.Connection):
                add_column_if_missing(c, "search_docs", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_tenant
                    ON search_docs(tenant_id);
                """)

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="initial_search_tables", up=_migrate_v1_tables_and_indexes),
                Migration(version=2, name="search_docs_tenant_id", up=_migrate_v2_tenant_id),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _embed_text(self, text: str) -> np.ndarray:
        """Lightweight deterministic feature hash embedder for local offline operation."""
        vec = np.zeros(self._dim, dtype=np.float32)
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec /= norm
        return vec

    def index_document(self, doc: SearchDocument) -> None:
        self.index_batch([doc])

    def index_batch(self, docs: List[SearchDocument]) -> int:
        if not docs:
            return 0

        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                for doc in docs:
                    # Ensure embedding exists
                    if doc.embedding is None:
                        emb = self._embed_text(f"{doc.title} {doc.content} {' '.join(doc.tags)}")
                        doc.embedding = emb.tolist()
                    else:
                        emb = np.array(doc.embedding, dtype=np.float32)

                    self._docs[doc.id] = doc
                    self._vectors[doc.id] = emb

                    tags_str = " ".join(doc.tags)
                    # Upsert metadata table
                    conn.execute(
                        """
                        INSERT INTO search_docs (
                            id, tenant_id, corpus_type, project_id, title, content, tags, metadata, embedding_json, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            tenant_id = excluded.tenant_id,
                            corpus_type = excluded.corpus_type,
                            project_id = excluded.project_id,
                            title = excluded.title,
                            content = excluded.content,
                            tags = excluded.tags,
                            metadata = excluded.metadata,
                            embedding_json = excluded.embedding_json,
                            timestamp = excluded.timestamp
                        """,
                        (
                            doc.id,
                            getattr(doc, "tenant_id", "default") or "default",
                            doc.corpus_type.value,
                            doc.project_id,
                            doc.title,
                            doc.content,
                            json.dumps(doc.tags),
                            json.dumps(doc.metadata),
                            json.dumps(doc.embedding),
                            doc.timestamp.isoformat() if hasattr(doc.timestamp, "isoformat") else now,
                        ),
                    )

                    # Update FTS5 table
                    conn.execute("DELETE FROM docs_fts WHERE id = ?", (doc.id,))
                    conn.execute(
                        """
                        INSERT INTO docs_fts (id, project_id, corpus_type, title, content, tags)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc.id,
                            doc.project_id,
                            doc.corpus_type.value,
                            doc.title,
                            doc.content,
                            tags_str,
                        ),
                    )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

        return len(docs)

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            self._docs.pop(doc_id, None)
            self._vectors.pop(doc_id, None)
            conn = self._get_connection()
            try:
                cur = conn.execute("DELETE FROM search_docs WHERE id = ?", (doc_id,))
                conn.execute("DELETE FROM docs_fts WHERE id = ?", (doc_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_by_project(self, project_id: str) -> int:
        with self._lock:
            to_remove = [did for did, d in self._docs.items() if d.project_id == project_id]
            for did in to_remove:
                self._docs.pop(did, None)
                self._vectors.pop(did, None)

            conn = self._get_connection()
            try:
                cur = conn.execute("DELETE FROM search_docs WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM docs_fts WHERE project_id = ?", (project_id,))
                conn.commit()
                return cur.rowcount
            finally:
                if self._memory_conn is None:
                    conn.close()

    def _lexical_search(self, query: SearchQuery) -> List[Tuple[SearchDocument, float]]:
        """Executes full-text BM25 search over SQLite FTS5."""
        # Sanitize query tokens for FTS5 syntax
        clean_terms = re.findall(r"\w+", query.query_text)
        if not clean_terms:
            return []

        fts_query = " OR ".join([f'"{t}"*' for t in clean_terms])

        sql = """
            SELECT id, rank
            FROM docs_fts
            WHERE docs_fts MATCH ? AND project_id = ?
        """
        params: list = [fts_query, query.project_id]

        if query.corpus_types:
            placeholders = ",".join(["?"] * len(query.corpus_types))
            sql += f" AND corpus_type IN ({placeholders})"
            params.extend([c.value for c in query.corpus_types])

        sql += " ORDER BY rank LIMIT ?"
        params.append(query.limit * 2)

        candidates: List[Tuple[SearchDocument, float]] = []
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(sql, params)
                for row in cur.fetchall():
                    did = row["id"]
                    doc = self._docs.get(did)
                    if doc:
                        # FTS5 bm25 rank is negative (lower = better match)
                        bm25_score = float(row["rank"])
                        candidates.append((doc, -bm25_score))
            finally:
                if self._memory_conn is None:
                    conn.close()

        # Tag filtering in memory if requested
        if query.tags:
            target_tags = set(t.lower() for t in query.tags)
            candidates = [
                (doc, s) for (doc, s) in candidates
                if any(t.lower() in target_tags for t in doc.tags)
            ]

        return candidates

    def _vector_search(self, query: SearchQuery) -> List[Tuple[SearchDocument, float]]:
        """Executes in-memory cosine similarity search."""
        q_vec = self._embed_text(query.query_text)
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-8:
            return []

        candidates: List[Tuple[SearchDocument, float]] = []
        with self._lock:
            for doc_id, doc in self._docs.items():
                if doc.project_id != query.project_id:
                    continue
                if query.corpus_types and doc.corpus_type not in query.corpus_types:
                    continue
                if query.tags:
                    target_tags = set(t.lower() for t in query.tags)
                    if not any(t.lower() in target_tags for t in doc.tags):
                        continue

                d_vec = self._vectors.get(doc_id)
                if d_vec is not None:
                    d_norm = np.linalg.norm(d_vec)
                    if d_norm > 1e-8:
                        cosine = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
                        candidates.append((doc, cosine))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[: query.limit * 2]

    def search(self, query: SearchQuery) -> SearchResponse:
        """Executes hybrid retrieval combining lexical FTS5 and vector similarity via RRF."""
        lexical_hits = self._lexical_search(query)
        vector_hits = self._vector_search(query)

        fused_results = self._rrf.fuse(
            lexical_hits=lexical_hits,
            vector_hits=vector_hits,
            k=60,
            alpha=query.hybrid_alpha,
            limit=query.limit,
        )

        return SearchResponse(
            query=query.query_text,
            tenant_id=query.tenant_id,
            project_id=query.project_id,
            total_hits=len(fused_results),
            results=fused_results,
        )
