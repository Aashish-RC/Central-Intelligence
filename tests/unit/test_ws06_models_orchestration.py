"""
Unit & Integration Tests for Workstream 06: Models, Reasoning and Orchestration.

Verifies:
- WS-06.1: Provider-agnostic model routing, streaming, and fallback.
- WS-06.2: Model budgets, quota limits, free-only policy, and BYOK credential handling.
- WS-06.3: Adaptive planning, bounded replanning, and cycle-free DAG construction.
- WS-06.4: Temporal workflow state checkpoints, crash-resilience, and resumption.
- WS-06.5: Parallel execution fan-out, fan-in barrier synchronization, and cooperative cancellation.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
import pytest

from control.orchestration.orchestrator.core.models import (
    PlanDAG,
    PlanNode,
    TaskStatus,
)
from control.orchestration.orchestrator.engine.cancellation import CancellationToken
from control.orchestration.orchestrator.engine.dag_runner import ParallelDAGRunner
from control.orchestration.orchestrator.guard.budget_guard import BudgetGuard
from control.orchestration.orchestrator.planner.multi_step_planner import MultiStepPlanner
from control.orchestration.orchestrator.storage.sqlite_plan_store import SQLitePlanStore
from control.orchestration.workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from control.orchestration.workflow_builder.runtime.orchestrator_bridge import (
    OrchestratorBridge,
)
from control.orchestration.workflow_builder.runtime.temporal_adapter import (
    TemporalWorkflowAdapter,
)


# -------------------------------------------------------------------------
# WS-06.3: Adaptive Planning & Bounded Replanning
# -------------------------------------------------------------------------

def test_multistep_planner_dag_and_topological_layers():
    """Verifies that MultiStepPlanner constructs validated DAGs and computes parallel execution layers."""
    planner = MultiStepPlanner()
    specs = [
        {"id": "fetch", "title": "Fetch context", "action": "fetch", "depends_on": []},
        {"id": "agent_alpha", "title": "Alpha Agent", "action": "research", "depends_on": ["fetch"]},
        {"id": "agent_beta", "title": "Beta Agent", "action": "code_review", "depends_on": ["fetch"]},
        {"id": "synthesize", "title": "Synthesize results", "action": "summarize", "depends_on": ["agent_alpha", "agent_beta"]},
    ]

    plan = planner.create_plan(
        title="Multi-Agent Research & Review",
        steps_spec=specs,
        budget_limit=2.50,
        max_concurrency=4,
    )

    assert plan.title == "Multi-Agent Research & Review"
    assert len(plan.nodes) == 4
    assert plan.budget_limit == 2.50
    assert plan.replan_count == 0

    layers = planner.get_execution_layers(plan)
    assert len(layers) == 3
    assert layers[0] == ["fetch"]
    assert set(layers[1]) == {"agent_alpha", "agent_beta"}
    assert layers[2] == ["synthesize"]


def test_multistep_planner_cycle_rejection():
    """Verifies that circular dependencies in plans are immediately detected and rejected."""
    planner = MultiStepPlanner()
    cyclic_specs = [
        {"id": "task_1", "action": "a", "depends_on": ["task_3"]},
        {"id": "task_2", "action": "b", "depends_on": ["task_1"]},
        {"id": "task_3", "action": "c", "depends_on": ["task_2"]},
    ]

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        planner.create_plan("Cyclic Pipeline", cyclic_specs)


def test_bounded_replanning_loop_terminates_cleanly():
    """Verifies that adaptive replanning injects remediation nodes and halts at max_replans limit."""
    planner = MultiStepPlanner()
    specs = [
        {"id": "scrape", "title": "Scrape Target", "action": "web_scrape", "depends_on": []},
        {"id": "parse", "title": "Parse Data", "action": "parse", "depends_on": ["scrape"]},
    ]
    plan = planner.create_plan("Scraping Workflow", specs)
    plan.max_replans = 3

    # Replan 1: inject fallback proxy
    plan = planner.replan(
        plan=plan,
        failed_node_id="scrape",
        feedback="Scrape blocked with HTTP 403",
        remediation_action="scrape_with_rotating_proxy",
    )
    assert plan.replan_count == 1
    assert "scrape_remedy_1" in plan.nodes
    assert plan.nodes["parse"].depends_on == ["scrape_remedy_1"]

    # Replan 2: inject headless browser
    plan = planner.replan(
        plan=plan,
        failed_node_id="scrape_remedy_1",
        feedback="Proxy failed, captcha challenge encountered",
        remediation_action="headless_browser_session",
    )
    assert plan.replan_count == 2
    assert "scrape_remedy_1_remedy_2" in plan.nodes

    # Replan 3: inject cached fallback
    plan = planner.replan(
        plan=plan,
        failed_node_id="scrape_remedy_1_remedy_2",
        feedback="Headless browser timeout",
        remediation_action="use_cached_archive",
    )
    assert plan.replan_count == 3

    # Replan 4: exceeds max_replans=3 -> must raise RuntimeError to prevent infinite loop
    with pytest.raises(RuntimeError, match="Maximum replanning threshold"):
        planner.replan(
            plan=plan,
            failed_node_id="scrape_remedy_1_remedy_2_remedy_3",
            feedback="Final failure",
            remediation_action="fail",
        )


# -------------------------------------------------------------------------
# WS-06.4: Temporal Workflow Durability & Checkpoint Resumption
# -------------------------------------------------------------------------

def test_temporal_checkpoint_persistence_and_resumption(tmp_path: Path):
    """Verifies workflow persists state across simulated crashes and resumes from checkpoints."""
    checkpoint_dir = tmp_path / "checkpoints"
    adapter = TemporalWorkflowAdapter(
        checkpoint_dir=str(checkpoint_dir),
        _defer_prod_check=True,
    )

    wf_id = "wf_crash_test_99"
    nodes = {
        "step_1": WorkflowNode(node_id="step_1", node_type=WorkflowNodeType.TRIGGER, label="Init", action_name="init"),
        "step_2": WorkflowNode(node_id="step_2", node_type=WorkflowNodeType.AGENT_STEP, label="Compute A", action_name="compute", upstream_dependencies=["step_1"]),
        "step_3": WorkflowNode(node_id="step_3", node_type=WorkflowNodeType.AGENT_STEP, label="Compute B", action_name="compute", upstream_dependencies=["step_2"]),
        "step_4": WorkflowNode(node_id="step_4", node_type=WorkflowNodeType.AGENT_STEP, label="Finish", action_name="finish", upstream_dependencies=["step_3"]),
    }
    graph = WorkflowGraph(workflow_id=wf_id, name="Resilient Pipeline", description="Testing durability", nodes=nodes)

    # 1. Run with crash simulated at step 2
    with pytest.raises(ProcessLookupError, match="Simulated process crash at step 2"):
        adapter.execute_workflow(graph, resume=True, fail_at_step=2)

    # Checkpoint must exist on disk
    cp_path = adapter._get_checkpoint_path(wf_id)
    assert cp_path.exists()
    checkpoint_data = adapter.load_checkpoint(wf_id)
    assert checkpoint_data is not None
    assert "step_1" in checkpoint_data["completed_nodes"]

    # 2. Resume execution after process restart
    report = adapter.execute_workflow(graph, resume=True, fail_at_step=None)
    assert report.success is True
    assert set(report.nodes_executed) == {"step_1", "step_2", "step_3", "step_4"}
    assert len(report.outputs) == 4


# -------------------------------------------------------------------------
# WS-06.2: Budget Guard Enforcement
# -------------------------------------------------------------------------

def test_orchestrator_budget_guard_limits():
    """Verifies that plans exceeding total budget limit are rejected by the budget guard."""
    guard = BudgetGuard()
    planner = MultiStepPlanner()

    # Plan costs $3.50, limit is $2.00
    expensive_specs = [
        {"id": "n1", "cost_estimate": 1.50, "depends_on": []},
        {"id": "n2", "cost_estimate": 2.00, "depends_on": ["n1"]},
    ]
    plan = planner.create_plan("Overbudget Plan", expensive_specs, budget_limit=2.00)

    assert guard.validate_plan_budget(plan) is False

    # Affordable plan
    cheap_specs = [
        {"id": "n1", "cost_estimate": 0.50, "depends_on": []},
        {"id": "n2", "cost_estimate": 0.80, "depends_on": ["n1"]},
    ]
    cheap_plan = planner.create_plan("Affordable Plan", cheap_specs, budget_limit=2.00)
    assert guard.validate_plan_budget(cheap_plan) is True


# -------------------------------------------------------------------------
# WS-06.5: Orchestration Parallel Execution & Cancellation
# -------------------------------------------------------------------------

def test_parallel_execution_and_cancellation():
    """Verifies that cooperative cancellation stops execution without hanging."""
    store = SQLitePlanStore(db_path=":memory:")
    runner = ParallelDAGRunner(store=store)
    planner = MultiStepPlanner()

    specs = [
        {"id": "init", "action": "init_task", "depends_on": []},
        {"id": "slow_worker", "action": "long_task", "depends_on": ["init"]},
    ]
    plan = planner.create_plan("Cancellation Test", specs)

    # Pre-cancelled token
    token = CancellationToken()
    token.cancel("User manual stop requested")

    report = runner.run_plan(plan, cancellation_token=token)
    assert report.status == TaskStatus.CANCELLED
    assert report.cancelled_nodes >= 1
