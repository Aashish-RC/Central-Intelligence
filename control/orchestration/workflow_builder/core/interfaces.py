"""Abstract interfaces for Pheonix Workflow Builder components."""

from abc import ABC, abstractmethod
from typing import List, Tuple
from .models import (
    DescribeWorkflowRequest,
    WorkflowBuildResult,
    WorkflowExecutionReport,
    WorkflowGraph,
)


class BaseWorkflowEngine(ABC):
    """Interface for managing and validating workflow topologies."""

    @abstractmethod
    def validate_graph(self, graph: WorkflowGraph) -> Tuple[bool, List[str]]:
        """Returns (is_valid, validation_errors). Checks cycles, missing dependencies, and connectivity."""
        pass


class BaseDescribeToWorkflowCompiler(ABC):
    """Interface for compiling plain language prompts into WorkflowGraphs."""

    @abstractmethod
    def compile_workflow(self, request: DescribeWorkflowRequest) -> WorkflowBuildResult:
        pass


class BaseOrchestratorBridge(ABC):
    """Interface for executing compiled workflows through the Orchestrator."""

    @abstractmethod
    def execute_workflow(
        self, graph: WorkflowGraph, initial_input: str
    ) -> WorkflowExecutionReport:
        pass
