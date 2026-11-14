"""Tier 4: Memgraph Knowledge Graph Store Adapter (opt-in self-hosted BSL-1.1).

Provides entity-relationship storage, multi-hop Cypher queries,
and conflict resolution against knowledge graphs.
Supports both live Memgraph instances via gqlalchemy/bolt and
deterministic in-memory execution via the shared NetworkXGraphFallback.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from cognitive.memory.core.exceptions import AdapterConnectionError
from cognitive.memory.core.interfaces import BaseGraphStore
from cognitive.memory.tiers.graph._nx_fallback import NetworkXGraphFallback, utc_now_str


class MemgraphAdapter(BaseGraphStore):
    """Opt-in self-hosted graph memory tier powered by Memgraph (with NetworkX fallback)."""

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

        self._fallback = NetworkXGraphFallback()
        self._nx_graph = self._fallback.graph

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
        return self._fallback.node_id(user_id, name, project_id)

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
        now = utc_now_str()
        self._fallback.add_entity(
            user_id=user_id,
            name=name,
            entity_type=entity_type,
            properties=props,
            project_id=project_id,
        )

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
        now = utc_now_str()
        result = self._fallback.add_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            properties=props,
            project_id=project_id,
        )

        if not self._is_in_memory and self._client:
            rel_clean = result["relation"]
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

        return result

    def delete_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Remove or deactivate a relationship (used in conflict resolution)."""
        removed = self._fallback.delete_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            project_id=project_id,
        )

        if not self._is_in_memory and self._client:
            rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper())
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
        return self._fallback.multi_hop_query(
            user_id=user_id,
            start_entity=start_entity,
            relation=relation,
            hops=hops,
            project_id=project_id,
        )

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

        return self._fallback.emulate_cypher(query, params)

    def _emulate_cypher(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._fallback.emulate_cypher(query, params)

    def delete_by_user(self, user_id: str) -> int:
        """Purge all graph nodes and edges for a given user."""
        removed = self._fallback.delete_by_user(user_id)
        if not self._is_in_memory and self._client:
            cypher = "MATCH (n {user_id: $user_id}) DETACH DELETE n;"
            try:
                self._client.execute_query(cypher, {"user_id": user_id})
            except Exception:
                pass
        return removed
