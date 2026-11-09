"""Tier 4: Memgraph Knowledge Graph Store Adapter.

Provides entity-relationship storage, multi-hop Cypher queries,
and conflict resolution against knowledge graphs.
Supports both live Memgraph instances via gqlalchemy/bolt and
deterministic in-memory graph execution (using networkx) for hermetic offline testing.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import networkx as nx

from memory.core.interfaces import BaseGraphStore
from memory.core.exceptions import AdapterConnectionError


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemgraphAdapter(BaseGraphStore):
    """Production and local graph memory tier powered by Memgraph (or in-memory graph)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7687,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auto_fallback: bool = True,
    ):
        self._host = host
        self._port = port
        self._username = username or ""
        self._password = password or ""
        self._auto_fallback = auto_fallback
        self._is_in_memory = False
        self._client: Optional[Any] = None

        # In-memory graph fallback
        self._nx_graph = nx.MultiDiGraph()

        self._init_client()

    def _init_client(self) -> None:
        if self._host == ":memory:":
            self._is_in_memory = True
            return

        try:
            from gqlalchemy import Memgraph

            client = Memgraph(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            # Probe connection with a minimal query
            list(client.execute_and_fetch("RETURN 1 AS test;"))
            self._client = client
            self._is_in_memory = False
        except Exception as e:
            if self._auto_fallback:
                self._is_in_memory = True
            else:
                raise AdapterConnectionError(
                    f"Failed to connect to Memgraph at {self._host}:{self._port}: {e}"
                )

    def check_health(self) -> bool:
        """Check whether graph backend is reachable and functioning."""
        if self._is_in_memory:
            return True
        try:
            if not self._client:
                return False
            res = list(self._client.execute_and_fetch("RETURN 1 AS health;"))
            return len(res) > 0
        except Exception:
            return False

    @property
    def is_in_memory(self) -> bool:
        return self._is_in_memory

    def _node_id(self, user_id: str, name: str, project_id: str = "default") -> str:
        return f"{user_id}:{project_id}:{name.strip().lower()}"

    def add_entity(
        self,
        user_id: str,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> str:
        """Store or update an entity node."""
        props = properties or {}
        now = _utc_now_str()

        # Update in-memory graph
        nid = self._node_id(user_id, name, project_id)
        current_data = self._nx_graph.nodes.get(nid, {})
        new_data = {
            **current_data,
            **props,
            "name": name,
            "entity_type": entity_type,
            "user_id": user_id,
            "project_id": project_id,
            "updated_at": now,
        }
        if "created_at" not in new_data:
            new_data["created_at"] = now
        self._nx_graph.add_node(nid, **new_data)

        # Update live Memgraph if connected
        if not self._is_in_memory and self._client:
            clean_type = re.sub(r"[^A-Za-z0-9_]", "", entity_type) or "Entity"
            cypher = f"""
            MERGE (n:{clean_type} {{name: $name, user_id: $user_id, project_id: $project_id}})
            ON CREATE SET n += $props, n.created_at = $now, n.updated_at = $now
            ON MATCH SET n += $props, n.updated_at = $now
            RETURN n.name AS name;
            """
            try:
                list(
                    self._client.execute_and_fetch(
                        cypher,
                        {
                            "name": name,
                            "user_id": user_id,
                            "project_id": project_id,
                            "props": props,
                            "now": now,
                        },
                    )
                )
            except Exception as e:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Memgraph add_entity failed: {e}")

        return name

    def add_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Store or update a directed relationship between two entities."""
        props = properties or {}
        now = _utc_now_str()
        rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper()) or "RELATED_TO"

        # Ensure both entity nodes exist
        self.add_entity(user_id=user_id, name=source, project_id=project_id)
        self.add_entity(user_id=user_id, name=target, project_id=project_id)

        src_id = self._node_id(user_id, source, project_id)
        tgt_id = self._node_id(user_id, target, project_id)

        # In-memory edge
        self._nx_graph.add_edge(
            src_id,
            tgt_id,
            key=rel_clean,
            relation=rel_clean,
            source=source,
            target=target,
            user_id=user_id,
            project_id=project_id,
            properties=props,
            created_at=now,
            is_active=True,
        )

        # Live Memgraph
        if not self._is_in_memory and self._client:
            cypher = f"""
            MATCH (s {{name: $source, user_id: $user_id, project_id: $project_id}})
            MATCH (t {{name: $target, user_id: $user_id, project_id: $project_id}})
            MERGE (s)-[r:{rel_clean}]->(t)
            ON CREATE SET r += $props, r.created_at = $now, r.is_active = true
            ON MATCH SET r += $props, r.updated_at = $now, r.is_active = true
            RETURN s.name AS source, type(r) AS relation, t.name AS target;
            """
            try:
                list(
                    self._client.execute_and_fetch(
                        cypher,
                        {
                            "source": source,
                            "target": target,
                            "user_id": user_id,
                            "project_id": project_id,
                            "props": props,
                            "now": now,
                        },
                    )
                )
            except Exception as e:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Memgraph add_relationship failed: {e}")

        return {
            "source": source,
            "relation": rel_clean,
            "target": target,
            "properties": props,
            "is_active": True,
        }

    def delete_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Remove or deactivate a relationship (used in conflict resolution)."""
        pid = project_id or "default"
        src_id = self._node_id(user_id, source, pid)
        tgt_id = self._node_id(user_id, target, pid)
        rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper())

        # In-memory
        removed = False
        if self._nx_graph.has_edge(src_id, tgt_id, key=rel_clean):
            self._nx_graph.remove_edge(src_id, tgt_id, key=rel_clean)
            removed = True

        # Live Memgraph
        if not self._is_in_memory and self._client:
            cypher = f"""
            MATCH (s {{name: $source, user_id: $user_id}})-[r:{rel_clean}]->(t {{name: $target, user_id: $user_id}})
            DELETE r;
            """
            try:
                self._client.execute_query(
                    cypher,
                    {"source": source, "target": target, "user_id": user_id},
                )
                removed = True
            except Exception:
                pass

        return removed

    def multi_hop_query(
        self,
        user_id: str,
        start_entity: str,
        relation: Optional[str] = None,
        hops: int = 2,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Traverse graph up to N hops from start entity following relationships."""
        pid = project_id or "default"
        start_id = self._node_id(user_id, start_entity, pid)
        rel_filter = relation.strip().upper() if relation else None

        results = []
        visited = set()

        # BFS traversal
        queue = [(start_id, start_entity, 0, [start_entity])]
        while queue:
            curr_id, curr_name, depth, path = queue.pop(0)
            if depth >= hops:
                continue

            if curr_id in self._nx_graph:
                for _, neighbor_id, key, data in self._nx_graph.out_edges(curr_id, data=True, keys=True):
                    if not data.get("is_active", True):
                        continue
                    if rel_filter and data.get("relation") != rel_filter:
                        continue

                    neighbor_name = self._nx_graph.nodes[neighbor_id].get("name", neighbor_id.split(":")[-1])
                    new_path = path + [data.get("relation", key), neighbor_name]
                    edge_key = (curr_id, neighbor_id, key, depth)
                    if edge_key not in visited:
                        visited.add(edge_key)
                        results.append({
                            "source": curr_name,
                            "relation": data.get("relation", key),
                            "target": neighbor_name,
                            "depth": depth + 1,
                            "path": new_path,
                            "properties": data.get("properties", {}),
                        })
                        queue.append((neighbor_id, neighbor_name, depth + 1, new_path))

        return results

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query against Memgraph, or in-memory emulation."""
        params = params or {}

        if not self._is_in_memory and self._client:
            try:
                raw_results = self._client.execute_and_fetch(query, params)
                return [dict(row) for row in raw_results]
            except Exception as e:
                if not self._auto_fallback:
                    raise AdapterConnectionError(f"Memgraph query failed: {e}")

        # In-Memory Cypher Emulator for typical query patterns
        return self._emulate_cypher(query, params)

    def _emulate_cypher(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Emulate common Cypher queries on the in-memory graph."""
        q = query.strip()

        # Pattern: MATCH (m)-[:RELATION]->(a {name: 'Alice'}) RETURN m.name
        match_incoming = re.search(
            r"MATCH\s*\(\s*(\w+)\s*\)\s*-\s*\[\s*:?(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*(?:\{\s*name\s*:\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))\s*\}\s*)?\)",
            q,
            re.IGNORECASE,
        )
        if match_incoming:
            rel_type = match_incoming.group(2).upper()
            target_name = match_incoming.group(4) or params.get(match_incoming.group(5) or "", "")
            
            # Check for WHERE clause if target_name wasn't in pattern
            if not target_name:
                where_match = re.search(r"WHERE\s+\w+\.name\s*=\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))", q, re.IGNORECASE)
                if where_match:
                    target_name = where_match.group(1) or params.get(where_match.group(2) or "", "")

            results = []
            for u, v, key, data in self._nx_graph.edges(data=True, keys=True):
                if not data.get("is_active", True):
                    continue
                v_name = self._nx_graph.nodes[v].get("name", "")
                if rel_type and data.get("relation") != rel_type:
                    continue
                if target_name and v_name.lower() != target_name.lower():
                    continue

                u_name = self._nx_graph.nodes[u].get("name", "")
                results.append({
                    "m.name": u_name,
                    "manager": u_name,
                    "source": u_name,
                    "relation": data.get("relation", key),
                    "target": v_name,
                })
            return results

        # Pattern: MATCH (a {name: 'Alice'})-[:RELATION]->(b) RETURN b.name
        match_outgoing = re.search(
            r"MATCH\s*\(\s*(\w+)\s*(?:\{\s*name\s*:\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))\s*\}\s*)?\)\s*-\s*\[\s*:?(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*\)",
            q,
            re.IGNORECASE,
        )
        if match_outgoing:
            source_name = match_outgoing.group(2) or params.get(match_outgoing.group(3) or "", "")
            rel_type = match_outgoing.group(4).upper()

            if not source_name:
                where_match = re.search(r"WHERE\s+\w+\.name\s*=\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))", q, re.IGNORECASE)
                if where_match:
                    source_name = where_match.group(1) or params.get(where_match.group(2) or "", "")

            results = []
            for u, v, key, data in self._nx_graph.edges(data=True, keys=True):
                if not data.get("is_active", True):
                    continue
                u_name = self._nx_graph.nodes[u].get("name", "")
                if rel_type and data.get("relation") != rel_type:
                    continue
                if source_name and u_name.lower() != source_name.lower():
                    continue

                v_name = self._nx_graph.nodes[v].get("name", "")
                results.append({
                    "b.name": v_name,
                    "target": v_name,
                    "relation": data.get("relation", key),
                    "source": u_name,
                })
            return results

        # Return empty list if query did not match known in-memory emulator pattern
        return []

    def delete_by_user(self, user_id: str) -> int:
        """Purge all graph nodes and edges for a given user."""
        nodes_to_remove = [
            n for n, d in self._nx_graph.nodes(data=True) if d.get("user_id") == user_id
        ]
        for n in nodes_to_remove:
            self._nx_graph.remove_node(n)

        if not self._is_in_memory and self._client:
            cypher = "MATCH (n {user_id: $user_id}) DETACH DELETE n;"
            try:
                self._client.execute_query(cypher, {"user_id": user_id})
            except Exception:
                pass

        return len(nodes_to_remove)

