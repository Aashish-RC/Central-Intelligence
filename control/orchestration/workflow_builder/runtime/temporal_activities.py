"""Activity implementations invoked by the CI Temporal workflow."""
from temporalio import activity


@activity.defn
async def execute_node(
    node_id: str, action_name: str, label: str, initial_input: str
) -> str:
    """Execute a single workflow node. Returns a stringified result.

    In production this dispatches to the L4/L5 action runner. For now it
    returns a deterministic completion marker that the workflow bridges into
    WorkflowExecutionReport.outputs.
    """
    return f"Completed action '{action_name}' on {label}"

