"""Describe-to-Workflow Compiler: Compiles natural language specifications into validated WorkflowGraphs."""

import re
import time
from typing import Dict, List, Optional
from ..core.interfaces import (
    BaseDescribeToWorkflowCompiler,
    BaseWorkflowEngine,
)
from ..core.models import (
    DescribeWorkflowRequest,
    WorkflowBuildResult,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from ..engine.workflow_engine import WorkflowEngine


class DescribeToWorkflowCompiler(BaseDescribeToWorkflowCompiler):
    """Synthesizes structured workflow graphs from plain-language user requests."""

    def __init__(self, engine: Optional[BaseWorkflowEngine] = None):
        self.engine = engine or WorkflowEngine()

    def compile_workflow(self, request: DescribeWorkflowRequest) -> WorkflowBuildResult:
        start_time = time.perf_counter()
        notes: List[str] = []
        validation_errors: List[str] = []

        if not request.prompt or len(request.prompt.strip()) < 5:
            return WorkflowBuildResult(
                success=False,
                validation_errors=["Workflow prompt must be at least 5 characters."],
            )

        text = request.prompt.lower()
        wf_name = request.workflow_name or "Synthesized Workflow"
        nodes: Dict[str, WorkflowNode] = {}
        edges: List[WorkflowEdge] = []

        # 1. Synthesize Entry Trigger Node
        trigger_id = "node_trigger"
        trigger_node = WorkflowNode(
            node_id=trigger_id,
            node_type=WorkflowNodeType.TRIGGER,
            label="Workflow Entry Trigger",
            action_name="event_listener",
            parameters={"event_type": "webhook" if "webhook" in text or "push" in text else "manual_invocation"},
        )
        nodes[trigger_id] = trigger_node
        notes.append("Generated root trigger node.")

        # 2. Check for Parallel Fan-out Pattern
        is_parallel = any(p in text for p in ("in parallel", "concurrently", "both", "simultaneously"))
        last_nodes = [trigger_id]

        if is_parallel:
            fanout_id = "node_fanout"
            fanout_node = WorkflowNode(
                node_id=fanout_id,
                node_type=WorkflowNodeType.PARALLEL_FANOUT,
                label="Parallel Dispatcher",
                action_name="barrier_fanout",
                upstream_dependencies=[trigger_id],
            )
            nodes[fanout_id] = fanout_node
            edges.append(WorkflowEdge(source_node_id=trigger_id, target_node_id=fanout_id))

            # Branch A: Security Scan / Code Analysis
            branch_a_id = "node_branch_a_security"
            branch_a = WorkflowNode(
                node_id=branch_a_id,
                node_type=WorkflowNodeType.AGENT_STEP,
                label="Security Auditor Agent",
                action_name="run_agent",
                parameters={"agent_type": "security_auditor"},
                upstream_dependencies=[fanout_id],
            )
            nodes[branch_a_id] = branch_a
            edges.append(WorkflowEdge(source_node_id=fanout_id, target_node_id=branch_a_id))

            # Branch B: Linter / Quality Check
            branch_b_id = "node_branch_b_lint"
            branch_b = WorkflowNode(
                node_id=branch_b_id,
                node_type=WorkflowNodeType.AGENT_STEP,
                label="Code Linter Agent",
                action_name="run_agent",
                parameters={"agent_type": "code_linter"},
                upstream_dependencies=[fanout_id],
            )
            nodes[branch_b_id] = branch_b
            edges.append(WorkflowEdge(source_node_id=fanout_id, target_node_id=branch_b_id))

            # Aggregate Fan-in Barrier
            fanin_id = "node_fanin_aggregate"
            fanin_node = WorkflowNode(
                node_id=fanin_id,
                node_type=WorkflowNodeType.AGGREGATE_FANIN,
                label="Consensus Barrier",
                action_name="barrier_fanin",
                upstream_dependencies=[branch_a_id, branch_b_id],
            )
            nodes[fanin_id] = fanin_node
            edges.append(WorkflowEdge(source_node_id=branch_a_id, target_node_id=fanin_id))
            edges.append(WorkflowEdge(source_node_id=branch_b_id, target_node_id=fanin_id))

            notes.append("Synthesized parallel fan-out / fan-in execution topology.")
            last_nodes = [fanin_id]
        else:
            # Sequential Step
            step_seq_id = "node_sequential_step"
            step_seq = WorkflowNode(
                node_id=step_seq_id,
                node_type=WorkflowNodeType.AGENT_STEP,
                label="Primary Task Agent",
                action_name="run_agent",
                upstream_dependencies=last_nodes,
            )
            nodes[step_seq_id] = step_seq
            edges.append(WorkflowEdge(source_node_id=last_nodes[0], target_node_id=step_seq_id))
            notes.append("Synthesized sequential execution chain.")
            last_nodes = [step_seq_id]

        # 3. Add Termination / Notification Node
        terminal_id = "node_terminal_notify"
        terminal_node = WorkflowNode(
            node_id=terminal_id,
            node_type=WorkflowNodeType.TERMINATION,
            label="Complete & Notify",
            action_name="send_notification",
            upstream_dependencies=last_nodes,
        )
        nodes[terminal_id] = terminal_node
        for src in last_nodes:
            edges.append(WorkflowEdge(source_node_id=src, target_node_id=terminal_id))

        graph = WorkflowGraph(
            name=wf_name,
            description=request.prompt,
            nodes=nodes,
            edges=edges,
        )

        # Validate graph topology
        is_valid, errs = self.engine.validate_graph(graph)
        if not is_valid:
            validation_errors.extend(errs)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return WorkflowBuildResult(
            success=is_valid,
            workflow=graph if is_valid else None,
            compiler_notes=notes,
            validation_errors=validation_errors,
            compile_duration_ms=round(duration_ms, 2),
        )
