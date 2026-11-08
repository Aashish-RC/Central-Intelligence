"""Tests for OrchestratorBridge."""

import pytest
from workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from workflow_builder.runtime.orchestrator_bridge import OrchestratorBridge


def test_orchestrator_bridge_topological_execution():
    bridge = OrchestratorBridge()

    nodes = {
        "start": WorkflowNode(
            node_id="start",
            node_type=WorkflowNodeType.TRIGGER,
            label="Start Trigger",
            action_name="init_trigger",
        ),
        "fanout": WorkflowNode(
            node_id="fanout",
            node_type=WorkflowNodeType.PARALLEL_FANOUT,
            label="Fanout",
            action_name="parallel_split",
            upstream_dependencies=["start"],
        ),
        "agent_a": WorkflowNode(
            node_id="agent_a",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent A",
            action_name="agent_task_a",
            upstream_dependencies=["fanout"],
        ),
        "agent_b": WorkflowNode(
            node_id="agent_b",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent B",
            action_name="agent_task_b",
            upstream_dependencies=["fanout"],
        ),
        "fanin": WorkflowNode(
            node_id="fanin",
            node_type=WorkflowNodeType.AGGREGATE_FANIN,
            label="Barrier",
            action_name="barrier_join",
            upstream_dependencies=["agent_a", "agent_b"],
        ),
    }

    graph = WorkflowGraph(name="Test Topo", description="Testing", nodes=nodes)
    report = bridge.execute_workflow(graph, "test_input")

    assert report.success is True
    assert len(report.nodes_executed) == 5
    # Order: start before fanout, fanout before agents, agents before fanin
    start_idx = report.nodes_executed.index("start")
    fanout_idx = report.nodes_executed.index("fanout")
    fanin_idx = report.nodes_executed.index("fanin")
    assert start_idx < fanout_idx < fanin_idx
    assert report.parallel_branches_executed == 2


def test_orchestrator_bridge_execute_with_orchestrator():
    bridge = OrchestratorBridge()
    nodes = {
        "n1": WorkflowNode(
            node_id="n1",
            node_type=WorkflowNodeType.TRIGGER,
            label="Root Trigger",
            action_name="trigger",
        ),
        "n2": WorkflowNode(
            node_id="n2",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent Processing",
            action_name="process",
            upstream_dependencies=["n1"],
        ),
    }
    graph = WorkflowGraph(name="Orchestrator Exec Test", description="Testing DAG compilation", nodes=nodes)
    
    # Execute through orchestrator ParallelDAGRunner
    execution_result = bridge.execute_with_orchestrator(graph, project_id="test_proj")
    assert execution_result is not None
    assert execution_result.status.value == "completed"
    assert execution_result.total_nodes == 2
    assert execution_result.completed_nodes == 2
    # Verify individual node results
    assert "n1" in execution_result.node_results
    assert "n2" in execution_result.node_results
    assert execution_result.node_results["n1"].status.value == "completed"
    assert execution_result.node_results["n2"].status.value == "completed"

