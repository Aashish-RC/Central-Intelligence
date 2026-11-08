"""Core data models for Orchestrator PlanDAG, PlanNodes, Execution States, and Reports."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class PlanNode(BaseModel):
    """An individual execution node within a plan DAG."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    title: str = "Untitled Step"
    action: str = "noop"
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list, description="List of predecessor node IDs")
    status: TaskStatus = TaskStatus.PENDING
    cost_estimate: float = 0.0
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class PlanDAG(BaseModel):
    """A directed acyclic graph representing a multi-step task execution plan."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    project_id: str = "default"
    title: str = "Task Execution Plan"
    nodes: Dict[str, PlanNode] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    budget_limit: float = 1.0  # Max USD budget for this plan
    max_concurrency: int = 4   # Max parallel branches
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def add_node(self, node: PlanNode) -> None:
        self.nodes[node.id] = node

    def get_dependencies(self, node_id: str) -> List[PlanNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[dep_id] for dep_id in node.depends_on if dep_id in self.nodes]


class StepResult(BaseModel):
    """The outcome of executing a single PlanNode."""
    model_config = ConfigDict(extra="ignore")

    node_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class PlanExecutionReport(BaseModel):
    """Overall summary and metrics of a completed or stopped plan execution."""
    model_config = ConfigDict(extra="ignore")

    plan_id: str
    status: TaskStatus
    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    cancelled_nodes: int = 0
    total_cost: float = 0.0
    duration_ms: float = 0.0
    node_results: Dict[str, StepResult] = Field(default_factory=dict)
