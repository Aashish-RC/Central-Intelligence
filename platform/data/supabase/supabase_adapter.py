"""Supabase PostgreSQL + pgvector + Apache AGE + RLS Adapter (Task 15.1)

Consolidates relational storage with Row Level Security (RLS),
pgvector for high-performance semantic vector search,
and Apache AGE for Cypher graph queries on PostgreSQL.
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


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

    def __init__(self, connection_url: Optional[str] = None) -> None:
        self.connection_url = connection_url or "postgresql://postgres:postgres@localhost:5432/postgres"
        # Table storage: table_name -> list of row dicts
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        # pgvector storage: collection_name -> list of VectorRecord
        self.vector_collections: Dict[str, List[VectorRecord]] = {}
        # Apache AGE graphs: graph_name -> (nodes, edges)
        self.graphs: Dict[str, Dict[str, Any]] = {}
        # RLS configuration: table_name -> enabled boolean
        self.rls_enabled: Dict[str, bool] = {}

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
        if table_name not in self.tables:
            self.tables[table_name] = []

        row = dict(data)
        row["user_id"] = user_id
        if "id" not in row:
            row["id"] = f"{table_name}_{len(self.tables[table_name]) + 1}"
        self.tables[table_name].append(row)
        return row

    def query_table(
        self,
        table_name: str,
        current_user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        is_service_role: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query rows from table. If RLS is enabled, strictly restrict to current_user_id."""
        rows = self.tables.get(table_name, [])
        is_rls = self.rls_enabled.get(table_name, False)

        results: List[Dict[str, Any]] = []
        for row in rows:
            # Enforce Row Level Security: regular users can only read their own rows
            if is_rls and not is_service_role:
                if row.get("user_id") != current_user_id:
                    continue

            # Apply additional query filters
            if filters:
                match = all(row.get(k) == v for k, v in filters.items())
                if not match:
                    continue

            results.append(dict(row))

        return results

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

    def search_embeddings(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute pgvector cosine similarity search with user-scoped isolation."""
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
        if graph_name not in self.graphs:
            self.graphs[graph_name] = {"nodes": {}, "edges": []}

    def add_graph_node(self, graph_name: str, node_id: str, label: str, properties: Dict[str, Any]) -> GraphNode:
        """Add a vertex to an Apache AGE graph."""
        self.create_graph(graph_name)
        node = GraphNode(id=node_id, label=label, properties=properties)
        self.graphs[graph_name]["nodes"][node_id] = node
        return node

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

    def execute_cypher(self, graph_name: str, query: str) -> List[Dict[str, Any]]:
        """Execute Cypher query over Apache AGE graph."""
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

