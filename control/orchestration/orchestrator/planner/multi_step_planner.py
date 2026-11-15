"""Multi-Step Task Planner: Graph DAG construction, cycle detection, and parallel layer resolution."""

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set
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

    def replan(
        self,
        plan: PlanDAG,
        failed_node_id: str,
        feedback: str,
        remediation_action: Optional[str] = None,
        max_replans: Optional[int] = None,
    ) -> PlanDAG:
        """
        Bounded adaptive replanning (Feature 8.03).
        Enforces maximum replan threshold to prevent infinite replanning cycles.
        """
        limit = max_replans if max_replans is not None else plan.max_replans
        if plan.replan_count >= limit:
            raise RuntimeError(
                f"Maximum replanning threshold ({limit}) reached for plan '{plan.id}'; aborting to prevent infinite cycle."
            )
        if failed_node_id not in plan.nodes:
            raise ValueError(f"Failed node '{failed_node_id}' does not exist in plan '{plan.id}'.")

        plan.replan_count += 1
        failed_node = plan.nodes[failed_node_id]
        failed_node.status = TaskStatus.FAILED
        failed_node.error = feedback

        # If remediation action specified, inject recovery node
        if remediation_action:
            recovery_node_id = f"{failed_node_id}_remedy_{plan.replan_count}"
            recovery_node = PlanNode(
                id=recovery_node_id,
                title=f"Remediate: {failed_node.title}",
                action=remediation_action,
                params={"reason": feedback, "original_params": failed_node.params},
                depends_on=[failed_node_id],
                status=TaskStatus.PENDING,
            )
            plan.add_node(recovery_node)
            # Re-point downstream dependencies that relied on failed_node to recovery_node
            for nid, node in plan.nodes.items():
                if nid != recovery_node_id and failed_node_id in node.depends_on:
                    node.depends_on = [
                        recovery_node_id if dep == failed_node_id else dep
                        for dep in node.depends_on
                    ]

        plan.updated_at = utc_now()
        # Verify no cycles introduced
        self.get_execution_layers(plan)
        return plan
