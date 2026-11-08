"""Workflow Engine: Validates workflow graph topologies, acyclicity, and dependency consistency."""

from typing import Dict, List, Set, Tuple
from ..core.interfaces import BaseWorkflowEngine
from ..core.models import WorkflowGraph, WorkflowNodeType


class WorkflowEngine(BaseWorkflowEngine):
    """Engine responsible for structural validation and dependency graph verification."""

    def validate_graph(self, graph: WorkflowGraph) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not graph.nodes:
            errors.append("WorkflowGraph has no nodes defined.")
            return False, errors

        # 1. Verify existence of upstream dependencies
        for node_id, node in graph.nodes.items():
            for dep_id in node.upstream_dependencies:
                if dep_id not in graph.nodes:
                    errors.append(f"Node '{node_id}' references non-existent upstream dependency '{dep_id}'.")

        # 2. Verify edge endpoints
        for edge in graph.edges:
            if edge.source_node_id not in graph.nodes:
                errors.append(f"Edge references invalid source node '{edge.source_node_id}'.")
            if edge.target_node_id not in graph.nodes:
                errors.append(f"Edge references invalid target node '{edge.target_node_id}'.")

        # 3. Detect Cycles using DFS (Kahn's or White/Gray/Black graph coloring)
        visited: Dict[str, int] = {nid: 0 for nid in graph.nodes}  # 0: white, 1: gray, 2: black

        def has_cycle(nid: str) -> bool:
            visited[nid] = 1  # visiting
            for dep_id in graph.nodes[nid].upstream_dependencies:
                if dep_id not in visited:
                    continue
                if visited[dep_id] == 1:
                    return True
                if visited[dep_id] == 0:
                    if has_cycle(dep_id):
                        return True
            visited[nid] = 2  # visited
            return False

        for nid in graph.nodes:
            if visited[nid] == 0:
                if has_cycle(nid):
                    errors.append(f"Cycle detected involving node '{nid}'. Workflows must be directed acyclic graphs (DAG).")
                    break

        return len(errors) == 0, errors
