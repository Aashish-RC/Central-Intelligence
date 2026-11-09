"""Tests for TemporalWorkflowAdapter and durable workflow execution."""

import shutil
import tempfile
from pathlib import Path
import pytest

from workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from workflow_builder.engine.workflow_engine import WorkflowEngine
from workflow_builder.runtime.temporal_adapter import TemporalWorkflowAdapter


@pytest.fixture
def temp_checkpoint_dir():
    temp_dir = tempfile.mkdtemp(prefix="temporal_ckpt_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_graph():
    nodes = {
        "start": WorkflowNode(
            node_id="start",
            node_type=WorkflowNodeType.TRIGGER,
            label="Workflow Start",
            action_name="trigger_event",
            upstream_dependencies=[],
        ),
        "process": WorkflowNode(
            node_id="process",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent Processor",
            action_name="run_agent",
            upstream_dependencies=["start"],
        ),
        "review": WorkflowNode(
            node_id="review",
            node_type=WorkflowNodeType.TERMINATION,
            label="Workflow Completion",
            action_name="complete_workflow",
            upstream_dependencies=["process"],
        ),
    }
    edges = [
        WorkflowEdge(source_node_id="start", target_node_id="process"),
        WorkflowEdge(source_node_id="process", target_node_id="review"),
    ]
    return WorkflowGraph(
        workflow_id="wf_temporal_test_101",
        name="Temporal Durability Test",
        description="Testing crash recovery and durability replay",
        nodes=nodes,
        edges=edges,
    )


def test_temporal_adapter_initialization(temp_checkpoint_dir):
    adapter = TemporalWorkflowAdapter(
        target_host="localhost:7233",
        checkpoint_dir=temp_checkpoint_dir,
    )
    assert adapter.target_host == "localhost:7233"
    assert Path(temp_checkpoint_dir).exists()


def test_temporal_adapter_full_execution(temp_checkpoint_dir, sample_graph):
    adapter = TemporalWorkflowAdapter(checkpoint_dir=temp_checkpoint_dir)
    report = adapter.execute_workflow(sample_graph)

    assert report.success is True
    assert len(report.nodes_executed) == 3
    assert "start" in report.outputs
    assert "process" in report.outputs
    assert "review" in report.outputs

    checkpoint = adapter.load_checkpoint(sample_graph.workflow_id)
    assert checkpoint is not None
    assert set(checkpoint["completed_nodes"]) == {"start", "process", "review"}


def test_temporal_adapter_crash_and_resumption(temp_checkpoint_dir, sample_graph):
    # Process 1: Start workflow and simulate a crash at step 2
    adapter_p1 = TemporalWorkflowAdapter(checkpoint_dir=temp_checkpoint_dir)
    
    with pytest.raises(ProcessLookupError, match="Simulated process crash at step 2"):
        adapter_p1.execute_workflow(sample_graph, fail_at_step=2)

    # Verify state was preserved in checkpoint before crash
    checkpoint = adapter_p1.load_checkpoint(sample_graph.workflow_id)
    assert checkpoint is not None
    assert checkpoint["completed_nodes"] == ["start"]
    assert "start" in checkpoint["outputs"]
    assert "process" not in checkpoint["outputs"]

    # Process 2: Simulating new process restart with brand new adapter instance
    adapter_p2 = TemporalWorkflowAdapter(checkpoint_dir=temp_checkpoint_dir)
    resumed_report = adapter_p2.execute_workflow(sample_graph, resume=True)

    assert resumed_report.success is True
    assert "start" in resumed_report.nodes_executed
    assert "process" in resumed_report.nodes_executed
    assert "review" in resumed_report.nodes_executed
    assert len(resumed_report.outputs) == 3


def test_workflow_engine_durable_execution(temp_checkpoint_dir, sample_graph):
    engine = WorkflowEngine()
    engine.temporal_adapter = TemporalWorkflowAdapter(checkpoint_dir=temp_checkpoint_dir)

    report = engine.execute_graph(sample_graph, durable=True)
    assert report.success is True
    assert len(report.nodes_executed) == 3
