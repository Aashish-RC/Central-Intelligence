"""Pheonix Workflow Builder Engine."""

from .core.models import (
    DescribeWorkflowRequest,
    WorkflowBuildResult,
    WorkflowEdge,
    WorkflowExecutionReport,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from .core.interfaces import (
    BaseDescribeToWorkflowCompiler,
    BaseOrchestratorBridge,
    BaseWorkflowEngine,
)
from .engine.workflow_engine import WorkflowEngine
from .compiler.describe_to_workflow import DescribeToWorkflowCompiler
from .runtime.orchestrator_bridge import OrchestratorBridge


def to_plan_dag(
    workflow: WorkflowGraph,
    project_id: str = "default",
    budget_limit: float = 1.0,
):
    """Compiles a visual WorkflowGraph into an executable orchestrator PlanDAG."""
    return workflow.to_plan_dag(project_id=project_id, budget_limit=budget_limit)


__all__ = [
    "DescribeWorkflowRequest",
    "WorkflowBuildResult",
    "WorkflowEdge",
    "WorkflowExecutionReport",
    "WorkflowGraph",
    "WorkflowNode",
    "WorkflowNodeType",
    "BaseDescribeToWorkflowCompiler",
    "BaseOrchestratorBridge",
    "BaseWorkflowEngine",
    "WorkflowEngine",
    "DescribeToWorkflowCompiler",
    "OrchestratorBridge",
    "to_plan_dag",
]
