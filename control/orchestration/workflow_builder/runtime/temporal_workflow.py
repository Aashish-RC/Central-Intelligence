"""Temporal workflow definition for Central Intelligence DAG execution."""
from datetime import timedelta
from typing import Dict, List, Set
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ..core.models import WorkflowGraph, WorkflowNodeType


@workflow.defn
class CIDagWorkflow:
    """Executes a CI workflow graph durably on the Temporal worker."""

    @workflow.run
    async def run(self, graph_dict: Dict, initial_input: str = "") -> Dict:
        # Reconstruct graph from serialized dict
        graph = WorkflowGraph.from_dict(graph_dict)
        completed: Set[str] = set()
        outputs: Dict[str, str] = {}

        while True:
            ready = [
                nid for nid, node in graph.nodes.items()
                if nid not in completed
                and all(dep in completed for dep in node.upstream_dependencies)
            ]
            if not ready:
                break

            for current_id in ready:
                node = graph.nodes[current_id]
                # Each node executes as a Temporal activity so it is replayable
                result = await workflow.execute_activity(
                    "execute_node",
                    args=[current_id, node.action_name, node.label, initial_input],
                    start_to_close_timeout=timedelta(seconds=300),
                )
                completed.add(current_id)
                outputs[current_id] = result

        return {
            "workflow_id": graph.workflow_id,
            "nodes_executed": list(completed),
            "outputs": outputs,
            "success": True,
        }

