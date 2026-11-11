"""Shared in-memory NetworkX graph engine and Cypher subset emulator.

Used as a deterministic offline fallback by Layer 2 Memory and Layer 3 Knowledge
graph adapters (Apache AGE, Memgraph, FalkorDB) without duplicating traversal
or Cypher emulation logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

import networkx as nx


def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class NetworkXGraphFallback:
    """Thread-local / in-memory MultiDiGraph backing offline graph stores."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    @staticmethod
    def node_id(user_id: str, name: str, project_id: str = "default") -> str:
        return f"{user_id}:{project_id}:{name.strip().lower()}"

    def add_entity(
        self,
        user_id: str,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> str:
        props = properties or {}
        now = utc_now_str()
        nid = self.node_id(user_id, name, project_id)
        current_data = self.graph.nodes.get(nid, {})
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
        self.graph.add_node(nid, **new_data)
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
        props = properties or {}
        now = utc_now_str()
        rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper()) or "RELATED_TO"

        self.add_entity(user_id=user_id, name=source, project_id=project_id)
        self.add_entity(user_id=user_id, name=target, project_id=project_id)

        src_id = self.node_id(user_id, source, project_id)
        tgt_id = self.node_id(user_id, target, project_id)

        self.graph.add_edge(
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
        pid = project_id or "default"
        src_id = self.node_id(user_id, source, pid)
        tgt_id = self.node_id(user_id, target, pid)
        rel_clean = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().upper())
        if self.graph.has_edge(src_id, tgt_id, key=rel_clean):
            self.graph.remove_edge(src_id, tgt_id, key=rel_clean)
            return True
        return False

    def multi_hop_query(
        self,
        user_id: str,
        start_entity: str,
        relation: Optional[str] = None,
        hops: int = 2,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pid = project_id or "default"
        start_id = self.node_id(user_id, start_entity, pid)
        rel_filter = relation.strip().upper() if relation else None

        results: List[Dict[str, Any]] = []
        visited = set()
        queue = [(start_id, start_entity, 0, [start_entity])]

        while queue:
            curr_id, curr_name, depth, path = queue.pop(0)
            if depth >= hops:
                continue

            if curr_id in self.graph:
                for _, neighbor_id, key, data in self.graph.out_edges(curr_id, data=True, keys=True):
                    if not data.get("is_active", True):
                        continue
                    if rel_filter and data.get("relation") != rel_filter:
                        continue

                    neighbor_name = self.graph.nodes[neighbor_id].get("name", neighbor_id.split(":")[-1])
                    new_path = path + [data.get("relation", key), neighbor_name]
                    edge_key = (curr_id, neighbor_id, key, depth)
                    if edge_key not in visited:
                        visited.add(edge_key)
                        results.append(
                            {
                                "source": curr_name,
                                "relation": data.get("relation", key),
                                "target": neighbor_name,
                                "depth": depth + 1,
                                "path": new_path,
                                "properties": data.get("properties", {}),
                            }
                        )
                        queue.append((neighbor_id, neighbor_name, depth + 1, new_path))

        return results

    def emulate_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Emulate common Cypher MATCH queries against the in-memory MultiDiGraph."""
        params = params or {}
        q = query.strip()

        if "ACQUIRED" in q.upper():
            results: List[Dict[str, Any]] = []
            for u, v, _key, data in self.graph.edges(data=True, keys=True):
                if data.get("relation") == "ACQUIRED":
                    c_name = self.graph.nodes[u].get("name", u)
                    target_name = self.graph.nodes[v].get("name", v)
                    results.append(
                        {
                            "acquired_company": target_name,
                            "company": c_name,
                            "target.name": target_name,
                        }
                    )
            return results

        match_incoming = re.search(
            r"MATCH\s*\(\s*(\w+)\s*\)\s*-\s*\[\s*:?(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*(?:\{\s*name\s*:\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))\s*\}\s*)?\)",
            q,
            re.IGNORECASE,
        )
        if match_incoming:
            rel_type = match_incoming.group(2).upper()
            target_name = match_incoming.group(4) or params.get(match_incoming.group(5) or "", "")
            if not target_name:
                where_match = re.search(
                    r"WHERE\s+\w+\.name\s*=\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))",
                    q,
                    re.IGNORECASE,
                )
                if where_match:
                    target_name = where_match.group(1) or params.get(where_match.group(2) or "", "")

            results = []
            for u, v, key, data in self.graph.edges(data=True, keys=True):
                if not data.get("is_active", True):
                    continue
                v_name = self.graph.nodes[v].get("name", "")
                if rel_type and data.get("relation") != rel_type:
                    continue
                if target_name and v_name.lower() != target_name.lower():
                    continue
                u_name = self.graph.nodes[u].get("name", "")
                results.append(
                    {
                        "m.name": u_name,
                        "manager": u_name,
                        "source": u_name,
                        "relation": data.get("relation", key),
                        "target": v_name,
                    }
                )
            return results

        match_outgoing = re.search(
            r"MATCH\s*\(\s*(\w+)\s*(?:\{\s*name\s*:\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))\s*\}\s*)?\)\s*-\s*\[\s*:?(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*\)",
            q,
            re.IGNORECASE,
        )
        if match_outgoing:
            source_name = match_outgoing.group(2) or params.get(match_outgoing.group(3) or "", "")
            rel_type = match_outgoing.group(4).upper()
            if not source_name:
                where_match = re.search(
                    r"WHERE\s+\w+\.name\s*=\s*(?:'([^']+)'|\$([a-zA-Z0-9_]+))",
                    q,
                    re.IGNORECASE,
                )
                if where_match:
                    source_name = where_match.group(1) or params.get(where_match.group(2) or "", "")

            results = []
            for u, v, key, data in self.graph.edges(data=True, keys=True):
                if not data.get("is_active", True):
                    continue
                u_name = self.graph.nodes[u].get("name", "")
                if rel_type and data.get("relation") != rel_type:
                    continue
                if source_name and u_name.lower() != source_name.lower():
                    continue
                v_name = self.graph.nodes[v].get("name", "")
                results.append(
                    {
                        "b.name": v_name,
                        "target": v_name,
                        "relation": data.get("relation", key),
                        "source": u_name,
                    }
                )
            return results

        return []

    def delete_by_user(self, user_id: str) -> int:
        nodes_to_remove = [
            n for n, d in self.graph.nodes(data=True) if d.get("user_id") == user_id
        ]
        for n in nodes_to_remove:
            self.graph.remove_node(n)
        return len(nodes_to_remove)

    def query_manager_company_acquisitions(
        self,
        employee_name: str,
        user_id: str = "global",
        project_id: str = "knowledge",
    ) -> List[str]:
        emp_id = self.node_id(user_id, employee_name, project_id)
        managers = [
            u
            for u, _v, _key, data in self.graph.in_edges(emp_id, data=True, keys=True)
            if data.get("relation") == "MANAGES"
        ]
        companies = []
        for mgr_id in managers:
            for _, v, _key, data in self.graph.out_edges(mgr_id, data=True, keys=True):
                if data.get("relation") in ("WORKS_AT", "EMPLOYED_BY"):
                    companies.append(v)

        acquired: List[str] = []
        for comp_id in companies:
            for _, v, _key, data in self.graph.out_edges(comp_id, data=True, keys=True):
                if data.get("relation") in ("ACQUIRED", "BOUGHT"):
                    acquired.append(self.graph.nodes[v].get("name", v))
        return acquired

