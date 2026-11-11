"""Layer 3 Knowledge: FalkorDB GraphRAG Adapter (opt-in self-hosted SSPL-v1).

Enables entity-relationship traversal, GraphRAG multi-hop retrieval,
and Cypher queries across knowledge assets.
Supports live FalkorDB instance (Redis protocol / SSPL-1.0) and in-memory
execution via the shared NetworkXGraphFallback.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from memory.tiers.graph._nx_fallback import NetworkXGraphFallback, utc_now_str
except ModuleNotFoundError:  # pragma: no cover - root-only sys.path invocation
    from cognitive.memory.tiers.graph._nx_fallback import NetworkXGraphFallback, utc_now_str


class FalkorDBAdapter:
    """Opt-in GraphRAG knowledge graph adapter powered by FalkorDB."""

    _DEFAULT_USER = "global"
    _DEFAULT_PROJECT = "knowledge"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6380,
        graph_id: str = "knowledge_graph",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auto_fallback: bool = True,
    ):
        self._host = host
        self._port = port
        self._graph_id = graph_id
        self._username = username
        self._password = password
        self._auto_fallback = auto_fallback
        self._is_in_memory = False
        self._client: Optional[Any] = None
        self._graph: Optional[Any] = None

        self._fallback = NetworkXGraphFallback()
        self._nx_graph = self._fallback.graph

        self._init_client()

    def _init_client(self) -> None:
        if self._host == ":memory:":
            self._is_in_memory = True
            return

        try:
            from falkordb import FalkorDB

            db = FalkorDB(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            graph = db.select_graph(self._graph_id)
            graph.query("RETURN 1 AS test")
            self._client = db
            self._graph = graph
            self._is_in_memory = False
        except Exception:
            if self._auto_fallback:
                self._is_in_memory = True
            else:
                raise

    @property
    def is_in_memory(self) -> bool:
        return self._is_in_memory

    def check_health(self) -> bool:
        """Verify graph database connectivity."""
        if self._is_in_memory:
            return True
        try:
            if not self._graph:
                return False
            res = self._graph.query("RETURN 1 AS health")
            return res is not None
        except Exception:
            return False

    def add_entity(
        self,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or update an entity node in the knowledge graph."""
        props = properties or {}
        now = utc_now_str()
        self._fallback.add_entity(
            user_id=self._DEFAULT_USER,
            name=name,
            entity_type=entity_type,
            properties=props,
            project_id=self._DEFAULT_PROJECT,
        )

        if not self._is_in_memory and self._graph:
            clean_type = re.sub(r"[^A-Za-z0-9_]", "", entity_type) or "Entity"
            cypher = f"MERGE (n:{clean_type} {{name: $name}}) SET n += $props, n.updated_at = $now RETURN n.name"
            try:
                self._graph.query(cypher, {"name": name, "props": props, "now": now})
            except Exception:
                pass

        return name

    def add_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create or update a directed relationship between two entities."""
        props = properties or {}
        now = utc_now_str()
        result = self._fallback.add_relationship(
            user_id=self._DEFAULT_USER,
            source=source,
            relation=relation,
            target=target,
            properties=props,
            project_id=self._DEFAULT_PROJECT,
        )
        rel_clean = result["relation"]

        if not self._is_in_memory and self._graph:
            cypher = f"""
            MATCH (s {{name: $source}}), (t {{name: $target}})
            MERGE (s)-[r:{rel_clean}]->(t)
            SET r += $props, r.updated_at = $now
            RETURN s.name, type(r), t.name
            """
            try:
                self._graph.query(cypher, {"source": source, "target": target, "props": props, "now": now})
            except Exception:
                pass

        return {
            "source": source,
            "relation": rel_clean,
            "target": target,
            "properties": props,
        }

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query on FalkorDB or in-memory fallback."""
        params = params or {}
        if not self._is_in_memory and self._graph:
            try:
                res = self._graph.query(query, params)
                output = []
                for record in getattr(res, "result_set", []):
                    output.append(dict(zip(res.header, record)))
                return output
            except Exception:
                pass

        return self._fallback.emulate_cypher(query, params)

    def _emulate_cypher(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._fallback.emulate_cypher(query, params)

    def multi_hop_query(
        self,
        start_entity: str,
        hops: int = 3,
    ) -> List[Dict[str, Any]]:
        """BFS multi-hop traversal from start entity."""
        return self._fallback.multi_hop_query(
            user_id=self._DEFAULT_USER,
            start_entity=start_entity,
            hops=hops,
            project_id=self._DEFAULT_PROJECT,
        )

    def query_manager_company_acquisitions(self, employee_name: str) -> List[str]:
        """GraphRAG query: What companies does Alice's manager's company acquire?"""
        return self._fallback.query_manager_company_acquisitions(
            employee_name=employee_name,
            user_id=self._DEFAULT_USER,
            project_id=self._DEFAULT_PROJECT,
        )
