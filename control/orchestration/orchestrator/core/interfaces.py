"""Abstract interfaces for Planner, DAG Runner, Budget Guard, and Plan Store."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .models import (
    PlanDAG,
    PlanExecutionReport,
    PlanNode,
    StepResult,
    TaskStatus,
)


class BasePlanner(ABC):
    """Decomposes tasks into topologically sorted DAGs."""

    @abstractmethod
    def create_plan(
        self,
        title: str,
        steps_spec: List[Dict[str, Any]],
        project_id: str = "default",
        budget_limit: float = 1.0,
        max_concurrency: int = 4,
    ) -> PlanDAG:
        """Constructs and validates a PlanDAG from a step specification."""
        pass

    @abstractmethod
    def get_execution_layers(self, plan: PlanDAG) -> List[List[str]]:
        """Returns ordered layers of independent node IDs for parallel fan-out."""
        pass


class BaseDAGRunner(ABC):
    """Executes a PlanDAG with parallel fan-out, fan-in, and cooperative stop."""

    @abstractmethod
    def run_plan(self, plan: PlanDAG, cancellation_token: Optional[Any] = None) -> PlanExecutionReport:
        """Executes the plan DAG and returns a detailed execution report."""
        pass


class BaseBudgetGuard(ABC):
    """Enforces plan-level budget thresholds and concurrency constraints."""

    @abstractmethod
    def validate_plan_budget(self, plan: PlanDAG) -> bool:
        """Validates that total estimated plan cost does not exceed limit."""
        pass

    @abstractmethod
    def record_step_cost(self, plan_id: str, cost: float) -> bool:
        """Records actual incurred step cost against the plan."""
        pass


class BasePlanStore(ABC):
    """Persistent storage for plan state, checkpoints, and resumption."""

    @abstractmethod
    def save_plan(self, plan: PlanDAG) -> None:
        """Persists or updates a PlanDAG."""
        pass

    @abstractmethod
    def get_plan(self, plan_id: str) -> Optional[PlanDAG]:
        """Loads a PlanDAG by its ID."""
        pass

    @abstractmethod
    def update_node(
        self,
        plan_id: str,
        node_id: str,
        status: TaskStatus,
        output: Any = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Updates the status and output of a specific node."""
        pass

    @abstractmethod
    def update_plan_status(self, plan_id: str, status: TaskStatus) -> None:
        """Updates the status of an entire plan."""
        pass

