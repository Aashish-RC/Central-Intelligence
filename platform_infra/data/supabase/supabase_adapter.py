"""Supabase PostgreSQL + pgvector + Apache AGE + RLS Adapter (Task 15.1)

Consolidates relational storage with Row Level Security (RLS),
pgvector for high-performance semantic vector search,
and Apache AGE for Cypher graph queries on PostgreSQL.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)


@dataclass
class VectorRecord:
    """Vector record stored in pgvector extension."""
    id: str
    collection: str
    vector: List[float]
    document: str
    user_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphNode:
    """Apache AGE graph vertex."""
    id: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Apache AGE graph edge connecting vertices."""
    id: str
    label: str
    from_node: str
    to_node: str
    properties: Dict[str, Any] = field(default_factory=dict)


class SupabaseAdapter:
    """Consolidated PostgreSQL adapter with RLS, pgvector, and Apache AGE graph querying."""

    def __init__(self, connection_url: Optional[str] = None, _defer_prod_check: bool = False) -> None:
        self.connection_url = connection_url or "postgresql://postgres:postgres@localhost:5432/postgres"
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("supabase")
        )
        # Table storage: table_name -> list of row dicts
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        # pgvector storage: collection_name -> list of VectorRecord
        self.vector_collections: Dict[str, List[VectorRecord]] = {}
        # Apache AGE graphs: graph_name -> (nodes, edges)
        self.graphs: Dict[str, Dict[str, Any]] = {}
        # RLS configuration: table_name -> enabled boolean
        self.rls_enabled: Dict[str, bool] = {}

        # Live connections — initialized lazily
        self._pg_conn = None
        self._age_conn = None
        if self.adapter_mode == "live" and os.getenv("CI_TEST_MODE") != "1":
            self._ensure_live_backend()

    def _ensure_live_backend(self) -> None:
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        try:
            import pg8000
            u = urlparse(self.connection_url)
            self._pg_conn = pg8000.connect(
                host=u.hostname or "localhost",
                port=u.port or 5432,
                user=u.username or "postgres",
                password=u.password or "postgres",
                database=(u.path or "/postgres").lstrip("/") or "postgres",
                timeout=5.0,
            )
            cur = self._pg_conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("CREATE EXTENSION IF NOT EXISTS age")
            self._pg_conn.commit()
            cur.close()
        except ImportError:
            fail_closed_in_production(
                "supabase",
                "pg8000 not installed; pip install pg8000>=1.31.0",
            )
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"PostgreSQL connection to {self.connection_url} failed: {exc}",
                cause=exc,
            )

    def _get_conn(self):
        if self._pg_conn is None or getattr(self._pg_conn, "closed", False):
            self._ensure_live_backend()
        return self._pg_conn

    def _connect_age(self, age_url: str):
        import pg8000
        u = urlparse(age_url)
        conn = pg8000.connect(
            host=u.hostname or "localhost",
            port=u.port or 5433,
            user=u.username or "postgres",
            password=u.password or "postgres",
            database=(u.path or "/postgres").lstrip("/") or "postgres",
            timeout=5.0,
        )
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS age")
        cur.execute("LOAD 'age'")
        cur.execute("SET search_path = ag_catalog, '$user', public")
        conn.commit()
        cur.close()
        return conn

    def _get_age_conn(self):
        if self._age_conn is None or getattr(self._age_conn, "closed", False):
            if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
                return None
            try:
                age_url = self.connection_url.replace(":5432", ":5433")
                self._age_conn = self._connect_age(age_url)
            except ImportError:
                fail_closed_in_production("supabase", "pg8000 not installed")
            except Exception as exc:
                fail_closed_in_production(
                    "supabase",
                    f"Apache AGE connection failed: {exc}",
                    cause=exc,
                )
        return self._age_conn

    # -------------------------------------------------------------
    # 1. Relational Data with Row Level Security (RLS)
    # -------------------------------------------------------------
    def enable_rls(self, table_name: str) -> None:
        """Enable Row Level Security on a table."""
        self.rls_enabled[table_name] = True
        if table_name not in self.tables:
            self.tables[table_name] = []

    def insert_row(
        self,
        table_name: str,
        data: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """Insert a relational row associated with a user tenant."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            if table_name not in self.tables:
                self.tables[table_name] = []

            row = dict(data)
            row["user_id"] = user_id
            if "id" not in row:
                row["id"] = f"{table_name}_{len(self.tables[table_name]) + 1}"
            self.tables[table_name].append(row)
            return row

        row = dict(data)
        row["user_id"] = user_id
        if "id" not in row:
            row["id"] = f"{table_name}_{int(time.time()*1000)}"

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cols = list(row.keys())
            col_defs = ", ".join(
                f"{c} TEXT" if c != "id" else f"{c} TEXT PRIMARY KEY"
                for c in cols
            )
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})")
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})",
                [str(row[c]) if row[c] is not None else None for c in cols],
            )
            conn.commit()
            cur.close()
            return row
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"insert_row on {table_name} failed: {exc}",
                cause=exc,
            )

    def query_table(
        self,
        table_name: str,
        current_user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        is_service_role: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query rows from table. If RLS is enabled, strictly restrict to current_user_id."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            rows = self.tables.get(table_name, [])
            is_rls = self.rls_enabled.get(table_name, False)

            results: List[Dict[str, Any]] = []
            for row in rows:
                if is_rls and not is_service_role:
                    if row.get("user_id") != current_user_id:
                        continue
                if filters:
                    match = all(row.get(k) == v for k, v in filters.items())
                    if not match:
                        continue
                results.append(dict(row))
            return results

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [table_name],
            )
            exists = cur.fetchone()[0]
            if not exists:
                cur.close()
                return []

            sql = f"SELECT * FROM {table_name}"
            where_clauses = []
            params: List[Any] = []
            if self.rls_enabled.get(table_name) and not is_service_role:
                where_clauses.append("user_id = %s")
                params.append(current_user_id)
            if filters:
                for k, v in filters.items():
                    where_clauses.append(f"{k} = %s")
                    params.append(str(v))
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return rows
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"query_table on {table_name} failed: {exc}",
                cause=exc,
            )

    # -------------------------------------------------------------
    # 2. pgvector Semantic Search
    # -------------------------------------------------------------
    def store_embedding(
        self,
        collection: str,
        record_id: str,
        vector: List[float],
        document: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VectorRecord:
        """Insert or update a vector record in pgvector."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            if collection not in self.vector_collections:
                self.vector_collections[collection] = []

            record = VectorRecord(
                id=record_id,
                collection=collection,
                vector=vector,
                document=document,
                user_id=user_id,
                metadata=metadata or {},
            )
            self.vector_collections[collection].append(record)
            return record

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS vec_{collection} (
                    id TEXT PRIMARY KEY,
                    embedding vector({len(vector)}),
                    document TEXT,
                    user_id TEXT,
                    metadata JSONB
                )
            """)
            vector_literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
            cur.execute(
                f"INSERT INTO vec_{collection} (id, embedding, document, user_id, metadata) "
                f"VALUES (%s, %s, %s, %s, %s) "
                f"ON CONFLICT (id) DO UPDATE SET "
                f"embedding = EXCLUDED.embedding, document = EXCLUDED.document, "
                f"user_id = EXCLUDED.user_id, metadata = EXCLUDED.metadata",
                [
                    record_id,
                    vector_literal,
                    document,
                    user_id,
                    json.dumps(metadata or {}),
                ],
            )
            conn.commit()
            cur.close()
            return VectorRecord(
                id=record_id,
                collection=collection,
                vector=vector,
                document=document,
                user_id=user_id,
                metadata=metadata or {},
            )
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"store_embedding failed: {exc}",
                cause=exc,
            )

    def search_embeddings(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute pgvector cosine similarity search with user-scoped isolation."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            records = self.vector_collections.get(collection, [])
            scored: List[Tuple[float, VectorRecord]] = []

            for rec in records:
                if user_id and rec.user_id != user_id:
                    continue
                sim = self._cosine_similarity(query_vector, rec.vector)
                scored.append((sim, rec))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [
                {
                    "id": rec.id,
                    "document": rec.document,
                    "similarity": round(score, 4),
                    "metadata": rec.metadata,
                    "user_id": rec.user_id,
                }
                for score, rec in scored[:top_k]
            ]

        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [f"vec_{collection}"],
            )
            exists = cur.fetchone()[0]
            if not exists:
                cur.close()
                return []

            vector_literal = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
            sql = f"""
                SELECT id, document, metadata, user_id,
                       1 - (embedding <=> %s) AS similarity
                FROM vec_{collection}
            """
            params: List[Any] = [vector_literal]
            if user_id:
                sql += " WHERE user_id = %s"
                params.append(user_id)
            sql += " ORDER BY embedding <=> %s LIMIT %s"
            params.extend([vector_literal, top_k])

            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
            results = []
            for r in rows:
                meta = r[2]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                results.append({
                    "id": r[0],
                    "document": r[1],
                    "metadata": meta or {},
                    "user_id": r[3],
                    "similarity": round(float(r[4]), 4),
                })
            return results
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"search_embeddings failed: {exc}",
                cause=exc,
            )

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if len(v1) != len(v2) or not v1:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    # -------------------------------------------------------------
    # 3. Apache AGE Graph Engine
    # -------------------------------------------------------------
    def create_graph(self, graph_name: str) -> None:
        """Create an Apache AGE graph namespace."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            if graph_name not in self.graphs:
                self.graphs[graph_name] = {"nodes": {}, "edges": []}
            return

        try:
            conn = self._get_age_conn()
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s", [graph_name])
            if not cur.fetchall():
                cur.execute(f"SELECT create_graph('{graph_name}')")
                conn.commit()
            cur.close()
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"create_graph on {graph_name} failed: {exc}",
                cause=exc,
            )

    def add_graph_node(
        self, graph_name: str, node_id: str, label: str, properties: Dict[str, Any]
    ) -> GraphNode:
        """Add a vertex to an Apache AGE graph."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            self.create_graph(graph_name)
            node = GraphNode(id=node_id, label=label, properties=properties)
            self.graphs[graph_name]["nodes"][node_id] = node
            return node

        try:
            self.create_graph(graph_name)
            conn = self._get_age_conn()
            cur = conn.cursor()
            props = dict(properties)
            props["id"] = node_id
            props_json = json.dumps(props)
            cypher = f"CREATE (:{label} {props_json})"
            cur.execute(f"SELECT * FROM cypher('{graph_name}', $${cypher}$$) AS (v agtype)")
            conn.commit()
            cur.close()
            return GraphNode(id=node_id, label=label, properties=properties)
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"add_graph_node on {graph_name} failed: {exc}",
                cause=exc,
            )

    def add_graph_edge(
        self,
        graph_name: str,
        edge_id: str,
        label: str,
        from_node: str,
        to_node: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> GraphEdge:
        """Add an edge to an Apache AGE graph."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            self.create_graph(graph_name)
            edge = GraphEdge(
                id=edge_id,
                label=label,
                from_node=from_node,
                to_node=to_node,
                properties=properties or {},
            )
            self.graphs[graph_name]["edges"].append(edge)
            return edge

        try:
            self.create_graph(graph_name)
            conn = self._get_age_conn()
            cur = conn.cursor()
            props = dict(properties or {})
            props["id"] = edge_id
            props_json = json.dumps(props)
            cypher = (
                f"MATCH (a {{id: '{from_node}'}}), (b {{id: '{to_node}'}}) "
                f"CREATE (a)-[r:{label} {props_json}]->(b)"
            )
            cur.execute(f"SELECT * FROM cypher('{graph_name}', $${cypher}$$) AS (e agtype)")
            conn.commit()
            cur.close()
            return GraphEdge(
                id=edge_id,
                label=label,
                from_node=from_node,
                to_node=to_node,
                properties=properties or {},
            )
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"add_graph_edge on {graph_name} failed: {exc}",
                cause=exc,
            )

    def execute_cypher(self, graph_name: str, query: str) -> List[Dict[str, Any]]:
        """Execute Cypher query over Apache AGE graph."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            graph = self.graphs.get(graph_name)
            if not graph:
                return []

            # Simple Cypher MATCH parser for pattern: MATCH (n:Label)-[r:REL]->(m)
            results: List[Dict[str, Any]] = []
            match_pattern = re.search(r'MATCH\s+\((\w+)(?::(\w+))?\)(?:-\[(\w+)(?::(\w+))?\]->\((\w+)(?::(\w+))?\))?', query, re.IGNORECASE)

            if match_pattern:
                node1_var = match_pattern.group(1)
                node1_label = match_pattern.group(2)
                rel_var = match_pattern.group(3)
                rel_label = match_pattern.group(4)
                node2_var = match_pattern.group(5)
                node2_label = match_pattern.group(6)

                if rel_label and node2_var:
                    for edge in graph["edges"]:
                        if edge.label == rel_label:
                            n1 = graph["nodes"].get(edge.from_node)
                            n2 = graph["nodes"].get(edge.to_node)
                            if n1 and n2:
                                if not node1_label or n1.label == node1_label:
                                    if not node2_label or n2.label == node2_label:
                                        results.append({
                                            node1_var: n1.properties,
                                            rel_var or "rel": edge.label,
                                            node2_var: n2.properties,
                                        })
                else:
                    for node in graph["nodes"].values():
                        if not node1_label or node.label == node1_label:
                            results.append({node1_var: node.properties})

            return results

        try:
            conn = self._get_age_conn()
            cur = conn.cursor()
            sql = f"SELECT * FROM cypher('{graph_name}', $${query}$$) AS (result agtype)"
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            return [{"result": r[0]} for r in rows]
        except Exception as exc:
            fail_closed_in_production(
                "supabase",
                f"execute_cypher on {graph_name} failed: {exc}",
                cause=exc,
            )
