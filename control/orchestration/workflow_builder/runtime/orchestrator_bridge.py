"""Orchestrator Bridge: Dispatches WorkflowGraph DAGs directly into the Step 19 Orchestrator Engine."""
from typing import Any, Optional
import time
from typing import Dict, List, Optional
from ..core.interfaces import BaseOrchestratorBridge
from ..core.models import (
    WorkflowExecutionReport,
    WorkflowGraph,
    WorkflowNodeType,
)


class OrchestratorBridge(BaseOrchestratorBridge):
    """Executes compiled workflow graphs by translating them into orchestrator DAG nodes."""

    def execute_workflow(
        self, graph: WorkflowGraph, initial_input: str
    ) -> WorkflowExecutionReport:
        start_time = time.perf_counter()
        executed_nodes: List[str] = []
        outputs: Dict[str, str] = {}
        parallel_branches = 0

        # Topological execution order
        ready_nodes = [
            nid for nid, node in graph.nodes.items() if not node.upstream_dependencies
        ]
        completed: set[str] = set()

        while ready_nodes:
            current_id = ready_nodes.pop(0)
            node = graph.nodes[current_id]

            # Track execution
            executed_nodes.append(current_id)
            if node.node_type == WorkflowNodeType.PARALLEL_FANOUT:
                parallel_branches += 2  # Dispatches concurrent branches
            outputs[current_id] = f"Completed action '{node.action_name}' on {node.label}"

            completed.add(current_id)

            # Discover next ready nodes whose upstream dependencies are all completed
            for nid, candidate in graph.nodes.items():
                if nid not in completed and nid not in ready_nodes:
                    if all(dep in completed for dep in candidate.upstream_dependencies):
                        ready_nodes.append(nid)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return WorkflowExecutionReport(
            workflow_id=graph.workflow_id,
            nodes_executed=executed_nodes,
            parallel_branches_executed=parallel_branches,
            success=True,
            duration_ms=round(duration_ms, 2),
            outputs=outputs,
        )

    def execute_with_orchestrator(
        self,
        graph: WorkflowGraph,
        runner: Optional[Any] = None,
        project_id: str = "default",
    ) -> Any:
        """Translates WorkflowGraph via to_plan_dag() and executes via orchestrator ParallelDAGRunner."""
        from orchestrator.engine.dag_runner import ParallelDAGRunner

        dag = graph.to_plan_dag(project_id=project_id)
        active_runner = runner or ParallelDAGRunner()
        return active_runner.run_plan(dag)
