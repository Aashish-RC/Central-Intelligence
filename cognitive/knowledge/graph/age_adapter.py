"""Layer 3 Knowledge: PostgreSQL + Apache AGE GraphRAG Adapter (OSI Default).

Provides the GraphRAG multi-hop knowledge graph interface over open-source
PostgreSQL + Apache AGE (Apache-2.0), delegating storage and Cypher execution
to Layer 2's shared ApacheAGEAdapter with deterministic NetworkX fallback.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter
except ModuleNotFoundError:  # pragma: no cover - root-only sys.path invocation
    from cognitive.memory.tiers.graph.age_adapter import ApacheAGEAdapter


class ApacheAGEGraphAdapter:
    """OSI-open default GraphRAG adapter backed by PostgreSQL + Apache AGE."""

    _DEFAULT_USER = "global"
    _DEFAULT_PROJECT = "knowledge"

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        graph_name: str = "ci_knowledge_graph",
        auto_fallback: bool = True,
    ) -> None:
        self._store = ApacheAGEAdapter(
            postgres_url=postgres_url,
            graph_name=graph_name,
            auto_fallback=auto_fallback,
        )
        self._nx_graph = self._store._nx_graph

    @property
    def is_in_memory(self) -> bool:
        return self._store.is_in_memory

    @property
    def graph_name(self) -> str:
        return self._store.graph_name

    def close(self) -> None:
        self._store.close()

    def check_health(self) -> bool:
        return self._store.check_health()

    def add_entity(
        self,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        return self._store.add_entity(
            user_id=self._DEFAULT_USER,
            name=name,
            entity_type=entity_type,
            properties=properties,
            project_id=self._DEFAULT_PROJECT,
        )

    def add_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        res = self._store.add_relationship(
            user_id=self._DEFAULT_USER,
            source=source,
            relation=relation,
            target=target,
            properties=properties,
            project_id=self._DEFAULT_PROJECT,
        )
        return {
            "source": res["source"],
            "relation": res["relation"],
            "target": res["target"],
            "properties": res["properties"],
        }

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self._store.execute_query(query, params=params)

    def multi_hop_query(
        self,
        start_entity: str,
        hops: int = 3,
    ) -> List[Dict[str, Any]]:
        return self._store.multi_hop_query(
            user_id=self._DEFAULT_USER,
            start_entity=start_entity,
            hops=hops,
            project_id=self._DEFAULT_PROJECT,
        )

    def query_manager_company_acquisitions(self, employee_name: str) -> List[str]:
        """Traverse employee <-[:MANAGES]- manager -[:WORKS_AT]-> company -[:ACQUIRED]-> target."""
        if not self.is_in_memory:
            rows = self.execute_query(
                "MATCH (e {name: $emp, user_id: $uid, project_id: $pid})"
                "<-[:MANAGES]-(m)-[:WORKS_AT]->(c)-[:ACQUIRED]->(target) "
                "RETURN target.name AS acquired",
                params={
                    "emp": employee_name,
                    "uid": self._DEFAULT_USER,
                    "pid": self._DEFAULT_PROJECT,
                },
            )
            if rows:
                return [str(row["acquired"]) for row in rows if row.get("acquired")]

        return self._store._fallback.query_manager_company_acquisitions(
            employee_name=employee_name,
            user_id=self._DEFAULT_USER,
            project_id=self._DEFAULT_PROJECT,
        )

