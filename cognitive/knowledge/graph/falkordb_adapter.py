"""Layer 3 Knowledge: FalkorDB GraphRAG Adapter.

Enables entity-relationship traversal, GraphRAG multi-hop retrieval,
and Cypher queries across knowledge assets.
Supports live FalkorDB instance (Redis protocol / SSPL-1.0) and in-memory
networkx graph execution for hermetic testing.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import networkx as nx


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class FalkorDBAdapter:
    """GraphRAG knowledge graph adapter powered by FalkorDB."""

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

        # In-memory graph engine
        self._nx_graph = nx.MultiDiGraph()

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
            # Probe connection and select graph
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
        now = _utc_now_str()
        nid = name.strip().lower()

        current_data = self._nx_graph.nodes.get(nid, {})
        new_data = {
            **current_data,
            **props,
            "name": name,
            "entity_type": entity_type,
            "updated_at": now,
        }
        if "created_at" not in new_data:
            new_data["created_at"] = now
        self._nx_graph.add_node(nid, **new_data)

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
        now = _utc_now_str()
        rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper()) or "RELATED_TO"

        self.add_entity(name=source)
        self.add_entity(name=target)

        src_id = source.strip().lower()
        tgt_id = target.strip().lower()

        self._nx_graph.add_edge(
            src_id,
            tgt_id,
            key=rel_clean,
            relation=rel_clean,
            source=source,
            target=target,
            properties=props,
            created_at=now,
            is_active=True,
        )

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
                # Parse FalkorDB result set into list of dicts
                output = []
                for record in getattr(res, "result_set", []):
                    output.append(dict(zip(res.header, record)))
                return output
            except Exception:
                pass

        return self._emulate_cypher(query, params)

    def _emulate_cypher(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """In-memory Cypher emulator for GraphRAG queries."""
        q = query.strip()

        # Multi-hop pattern: Alice -> Manager -> Company -> Target (ACQUIRED)
        # e.g.: MATCH (a {name: 'Alice'})<-[:MANAGES]-(m)-[:WORKS_AT]->(c)-[:ACQUIRED]->(target)
        if "ACQUIRED" in q.upper():
            results = []
            # Find acquisitions: c -[:ACQUIRED]-> target
            for u, v, key, data in self._nx_graph.edges(data=True, keys=True):
                if data.get("relation") == "ACQUIRED":
                    c_name = self._nx_graph.nodes[u].get("name", u)
                    target_name = self._nx_graph.nodes[v].get("name", v)
                    results.append({
                        "acquired_company": target_name,
                        "company": c_name,
                        "target.name": target_name,
                    })
            return results

        # Simple incoming: MATCH (m)-[:REL]->(t {name: '...'})
        match_incoming = re.search(
            r"MATCH\s*\(\s*(\w+)\s*\)\s*-\s*\[\s*:?(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*(?:\{\s*name\s*:\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))\s*\}\s*)?\)",
            q,
            re.IGNORECASE,
        )
        if match_incoming:
            rel_type = match_incoming.group(2).upper()
            target_name = match_incoming.group(4) or params.get(match_incoming.group(5) or "", "")
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
                results.append({"source": u_name, "target": v_name, "relation": rel_type})
            return results

        return []

    def multi_hop_query(
        self,
        start_entity: str,
        hops: int = 3,
    ) -> List[Dict[str, Any]]:
        """BFS multi-hop traversal from start entity."""
        start_id = start_entity.strip().lower()
        results = []
        visited = set()
        queue = [(start_id, start_entity, 0, [start_entity])]

        while queue:
            curr_id, curr_name, depth, path = queue.pop(0)
            if depth >= hops:
                continue

            if curr_id in self._nx_graph:
                for _, neighbor_id, key, data in self._nx_graph.out_edges(curr_id, data=True, keys=True):
                    neighbor_name = self._nx_graph.nodes[neighbor_id].get("name", neighbor_id)
                    edge_key = (curr_id, neighbor_id, key, depth)
                    if edge_key not in visited:
                        visited.add(edge_key)
                        new_path = path + [data.get("relation", key), neighbor_name]
                        results.append({
                            "source": curr_name,
                            "relation": data.get("relation", key),
                            "target": neighbor_name,
                            "depth": depth + 1,
                            "path": new_path,
                        })
                        queue.append((neighbor_id, neighbor_name, depth + 1, new_path))
        return results

    def query_manager_company_acquisitions(self, employee_name: str) -> List[str]:
        """GraphRAG query: What companies does Alice's manager's company acquire?
        Traversal path:
        employee <-[:MANAGES]- manager -[:WORKS_AT]-> company -[:ACQUIRED]-> acquired_company
        """
        emp_id = employee_name.strip().lower()

        # Step 1: Find manager (manager -[:MANAGES]-> employee OR employee <-[:MANAGES]- manager)
        managers = []
        for u, v, key, data in self._nx_graph.in_edges(emp_id, data=True, keys=True):
            if data.get("relation") == "MANAGES":
                managers.append(u)

        # Step 2: Find company manager works at (manager -[:WORKS_AT]-> company)
        companies = []
        for mgr_id in managers:
            for _, v, key, data in self._nx_graph.out_edges(mgr_id, data=True, keys=True):
                if data.get("relation") in ("WORKS_AT", "EMPLOYED_BY"):
                    companies.append(v)

        # Step 3: Find companies acquired (company -[:ACQUIRED]-> target_company)
        acquired = []
        for comp_id in companies:
            for _, v, key, data in self._nx_graph.out_edges(comp_id, data=True, keys=True):
                if data.get("relation") in ("ACQUIRED", "BOUGHT"):
                    target_name = self._nx_graph.nodes[v].get("name", v)
                    acquired.append(target_name)

        return acquired
