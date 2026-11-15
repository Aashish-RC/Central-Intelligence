"""Unit tests for MultiStepPlanner: DAG validation, topological layers, and cycle detection."""

import pytest
from orchestrator.planner.multi_step_planner import MultiStepPlanner


@pytest.fixture
def planner():
    return MultiStepPlanner()


def test_linear_plan_creation(planner):
    specs = [
        {"id": "step1", "title": "Fetch Data", "action": "fetch", "depends_on": []},
        {"id": "step2", "title": "Transform Data", "action": "transform", "depends_on": ["step1"]},
        {"id": "step3", "title": "Save Data", "action": "save", "depends_on": ["step2"]},
    ]
    plan = planner.create_plan("Linear Workflow", specs)
    assert len(plan.nodes) == 3

    layers = planner.get_execution_layers(plan)
    assert len(layers) == 3
    assert layers[0] == ["step1"]
    assert layers[1] == ["step2"]
    assert layers[2] == ["step3"]


def test_fanout_fanin_layers(planner):
    # Diamond graph:
    #        fetch
    #       /     \
    #   task_a   task_b
    #       \     /
    #      synthesize
    specs = [
        {"id": "fetch", "title": "Fetch", "depends_on": []},
        {"id": "task_a", "title": "Task A", "depends_on": ["fetch"]},
        {"id": "task_b", "title": "Task B", "depends_on": ["fetch"]},
        {"id": "synthesize", "title": "Synthesize", "depends_on": ["task_a", "task_b"]},
    ]
    plan = planner.create_plan("Diamond Workflow", specs)
    layers = planner.get_execution_layers(plan)

    assert len(layers) == 3
    assert layers[0] == ["fetch"]
    assert set(layers[1]) == {"task_a", "task_b"}
    assert layers[2] == ["synthesize"]


def test_cycle_detection(planner):
    specs = [
        {"id": "node_a", "depends_on": ["node_c"]},
        {"id": "node_b", "depends_on": ["node_a"]},
        {"id": "node_c", "depends_on": ["node_b"]},
    ]
    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        planner.create_plan("Circular Plan", specs)


def test_missing_dependency(planner):
    specs = [
        {"id": "node_a", "depends_on": ["missing_node_x"]},
    ]
    with pytest.raises(ValueError, match="non-existent node"):
        planner.create_plan("Invalid Plan", specs)


def test_adaptive_replanning_and_remediation(planner):
    specs = [
        {"id": "step1", "title": "Fetch", "action": "fetch", "depends_on": []},
        {"id": "step2", "title": "Process", "action": "process", "depends_on": ["step1"]},
    ]
    plan = planner.create_plan("Linear Workflow", specs)
    assert plan.replan_count == 0

    # Replan step1 with remediation
    replanned = planner.replan(
        plan=plan,
        failed_node_id="step1",
        feedback="Network timeout on remote fetch",
        remediation_action="fetch_with_backoff",
    )
    assert replanned.replan_count == 1
    assert "step1_remedy_1" in replanned.nodes
    # Downstream step2 now depends on the remedy node
    assert replanned.nodes["step2"].depends_on == ["step1_remedy_1"]


def test_bounded_replanning_loop_prevention(planner):
    specs = [
        {"id": "step1", "title": "Step 1", "action": "step1", "depends_on": []},
    ]
    plan = planner.create_plan("Looping Plan", specs)
    plan.max_replans = 2

    planner.replan(plan, "step1", "Error 1")
    planner.replan(plan, "step1", "Error 2")
    assert plan.replan_count == 2

    # 3rd replan must fail bounded check
    with pytest.raises(RuntimeError, match="Maximum replanning threshold"):
        planner.replan(plan, "step1", "Error 3")

