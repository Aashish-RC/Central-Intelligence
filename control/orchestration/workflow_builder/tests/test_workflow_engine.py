"""Tests for WorkflowEngine."""

import pytest
from workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from workflow_builder.engine.workflow_engine import WorkflowEngine


@pytest.fixture
def engine():
    return WorkflowEngine()


def test_validate_empty_graph(engine):
    graph = WorkflowGraph(name="Empty", description="No nodes")
    is_valid, errors = engine.validate_graph(graph)
    assert is_valid is False
    assert "no nodes defined" in errors[0].lower()


def test_validate_missing_dependency(engine):
    nodes = {
        "n1": WorkflowNode(
            node_id="n1",
            node_type=WorkflowNodeType.TRIGGER,
            label="Start",
            action_name="init",
            upstream_dependencies=["non_existent_node"],
        )
    }
    graph = WorkflowGraph(name="Bad Dep", description="Missing dep", nodes=nodes)
    is_valid, errors = engine.validate_graph(graph)
    assert is_valid is False
    assert "non-existent upstream dependency" in errors[0]


def test_validate_cycle_detection(engine):
    # A -> B -> A
    nodes = {
        "node_a": WorkflowNode(
            node_id="node_a",
            node_type=WorkflowNodeType.TRIGGER,
            label="A",
            action_name="a",
            upstream_dependencies=["node_b"],
        ),
        "node_b": WorkflowNode(
            node_id="node_b",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="B",
            action_name="b",
            upstream_dependencies=["node_a"],
        ),
    }
    edges = [
        WorkflowEdge(source_node_id="node_a", target_node_id="node_b"),
        WorkflowEdge(source_node_id="node_b", target_node_id="node_a"),
    ]
    graph = WorkflowGraph(name="Cyclic", description="Has cycle", nodes=nodes, edges=edges)
    is_valid, errors = engine.validate_graph(graph)
    assert is_valid is False
    assert any("cycle detected" in e.lower() for e in errors)


def test_validate_clean_dag(engine):
    nodes = {
        "n1": WorkflowNode(
            node_id="n1",
            node_type=WorkflowNodeType.TRIGGER,
            label="Start",
            action_name="init",
        ),
        "n2": WorkflowNode(
            node_id="n2",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Work",
            action_name="run",
            upstream_dependencies=["n1"],
        ),
    }
    edges = [WorkflowEdge(source_node_id="n1", target_node_id="n2")]
    graph = WorkflowGraph(name="Clean", description="Valid DAG", nodes=nodes, edges=edges)
    is_valid, errors = engine.validate_graph(graph)
    assert is_valid is True
    assert len(errors) == 0
