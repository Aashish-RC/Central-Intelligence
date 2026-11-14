"""Core data models for Pheonix Workflow Builder."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowNodeType(str, Enum):
    TRIGGER = "trigger"
    AGENT_STEP = "agent_step"
    TOOL_STEP = "tool_step"
    CONDITIONAL_BRANCH = "conditional_branch"
    PARALLEL_FANOUT = "parallel_fanout"
    AGGREGATE_FANIN = "aggregate_fanin"
    TERMINATION = "termination"


class WorkflowNode(BaseModel):
    node_id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:6]}")
    node_type: WorkflowNodeType
    label: str
    action_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    upstream_dependencies: List[str] = Field(default_factory=list)
    timeout_seconds: float = 60.0


class WorkflowEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    condition: Optional[str] = None


class WorkflowGraph(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    nodes: Dict[str, WorkflowNode] = Field(default_factory=dict)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "nodes": {
                nid: {
                    "node_id": n.node_id,
                    "action_name": n.action_name,
                    "label": n.label,
                    "node_type": n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type),
                    "parameters": n.parameters,
                    "upstream_dependencies": list(n.upstream_dependencies),
                    "timeout_seconds": n.timeout_seconds,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source_node_id": e.source_node_id,
                    "target_node_id": e.target_node_id,
                    "condition": e.condition,
                }
                for e in self.edges
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorkflowGraph":
        nodes = {}
        for nid, nd in d.get("nodes", {}).items():
            nt_val = nd.get("node_type", "agent_step")
            try:
                nt = WorkflowNodeType(nt_val)
            except ValueError:
                nt = WorkflowNodeType.AGENT_STEP
            nodes[nid] = WorkflowNode(
                node_id=nd.get("node_id", nid),
                node_type=nt,
                label=nd.get("label", nid),
                action_name=nd.get("action_name", ""),
                parameters=nd.get("parameters", {}),
                upstream_dependencies=nd.get("upstream_dependencies", []),
                timeout_seconds=float(nd.get("timeout_seconds", 60.0)),
            )
        edges = [
            WorkflowEdge(
                source_node_id=ed["source_node_id"],
                target_node_id=ed["target_node_id"],
                condition=ed.get("condition"),
            )
            for ed in d.get("edges", [])
        ]
        return cls(
            workflow_id=d.get("workflow_id", f"wf_{uuid.uuid4().hex[:8]}"),
            name=d.get("name", "workflow"),
            description=d.get("description", ""),
            nodes=nodes,
            edges=edges,
            metadata=d.get("metadata", {}),
        )

    def to_plan_dag(
        self,
        project_id: str = "default",
        budget_limit: float = 1.0,
    ) -> Any:
        """
        Compiles the visual WorkflowGraph into an executable orchestrator PlanDAG.
        Translates WorkflowNodes into PlanNodes and maps edge dependencies.
        """
        from orchestrator.core.models import PlanDAG, PlanNode, TaskStatus

        edge_deps: Dict[str, List[str]] = {}
        for edge in self.edges:
            edge_deps.setdefault(edge.target_node_id, []).append(edge.source_node_id)

        plan_nodes: Dict[str, PlanNode] = {}
        for nid, node in self.nodes.items():
            combined_deps = list(
                dict.fromkeys(node.upstream_dependencies + edge_deps.get(nid, []))
            )
            plan_nodes[nid] = PlanNode(
                id=nid,
                title=node.label or node.action_name,
                action=node.action_name,
                params={
                    **node.parameters,
                    "node_type": node.node_type.value,
                    "timeout_seconds": node.timeout_seconds,
                },
                depends_on=combined_deps,
                status=TaskStatus.PENDING,
            )

        return PlanDAG(
            id=self.workflow_id,
            project_id=project_id,
            title=self.name,
            nodes=plan_nodes,
            status=TaskStatus.PENDING,
            budget_limit=budget_limit,
        )


class DescribeWorkflowRequest(BaseModel):
    prompt: str
    workflow_name: Optional[str] = None
    domain: Optional[str] = None


class WorkflowBuildResult(BaseModel):
    success: bool
    workflow: Optional[WorkflowGraph] = None
    compiler_notes: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    compile_duration_ms: float = 0.0


class WorkflowExecutionReport(BaseModel):
    workflow_id: str
    nodes_executed: List[str] = Field(default_factory=list)
    parallel_branches_executed: int = 0
    success: bool = True
    duration_ms: float = 0.0
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
