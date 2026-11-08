"""Multi-Step Task Planner: Graph DAG construction, cycle detection, and parallel layer resolution."""

from collections import defaultdict, deque
from typing import Any, Dict, List, Set
from ..core.interfaces import BasePlanner
from ..core.models import PlanDAG, PlanNode, TaskStatus, utc_now


class MultiStepPlanner(BasePlanner):
    """Decomposes task specifications into validated, topologically layered PlanDAGs."""

    def create_plan(
        self,
        title: str,
        steps_spec: List[Dict[str, Any]],
        project_id: str = "default",
        budget_limit: float = 1.0,
        max_concurrency: int = 4,
    ) -> PlanDAG:
        nodes: Dict[str, PlanNode] = {}
        for s in steps_spec:
            node_id = str(s.get("id") or s.get("node_id"))
            node = PlanNode(
                id=node_id,
                title=s.get("title", f"Step {node_id}"),
                action=s.get("action", "noop"),
                params=s.get("params", {}),
                depends_on=[str(dep) for dep in s.get("depends_on", [])],
                status=TaskStatus.PENDING,
                cost_estimate=float(s.get("cost_estimate", 0.0)),
            )
            nodes[node_id] = node

        plan = PlanDAG(
            title=title,
            project_id=project_id,
            nodes=nodes,
            budget_limit=budget_limit,
            max_concurrency=max_concurrency,
            status=TaskStatus.PENDING,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        self._validate_dependencies(plan)
        # Check for cycles during construction
        self.get_execution_layers(plan)
        return plan

    def _validate_dependencies(self, plan: PlanDAG) -> None:
        all_ids = set(plan.nodes.keys())
        for node in plan.nodes.values():
            for dep in node.depends_on:
                if dep not in all_ids:
                    raise ValueError(f"Node '{node.id}' depends on non-existent node '{dep}'")

    def get_execution_layers(self, plan: PlanDAG) -> List[List[str]]:
        """Calculates topological execution layers for parallel fan-out using Kahn's algorithm."""
        in_degree: Dict[str, int] = {node_id: 0 for node_id in plan.nodes}
        graph: Dict[str, List[str]] = defaultdict(list)

        for node_id, node in plan.nodes.items():
            for dep in node.depends_on:
                graph[dep].append(node_id)
                in_degree[node_id] += 1

        # Nodes with 0 in-degree form the first layer
        current_layer = [n for n, deg in in_degree.items() if deg == 0]
        visited_count = 0
        layers: List[List[str]] = []

        while current_layer:
            layers.append(sorted(current_layer))
            visited_count += len(current_layer)
            next_layer = []
            for u in current_layer:
                for v in graph[u]:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        next_layer.append(v)
            current_layer = next_layer

        if visited_count != len(plan.nodes):
            raise ValueError("Cyclic dependency detected in task plan graph")

        return layers
