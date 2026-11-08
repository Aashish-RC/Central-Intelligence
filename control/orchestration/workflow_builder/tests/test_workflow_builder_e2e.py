"""End-to-End Tests for Workflow Builder: Verifies that a described workflow runs through the orchestrator."""

import pytest
from workflow_builder.core.models import (
    DescribeWorkflowRequest,
)
from workflow_builder.compiler.describe_to_workflow import DescribeToWorkflowCompiler
from workflow_builder.runtime.orchestrator_bridge import OrchestratorBridge


def test_described_workflow_runs_through_orchestrator():
    """Core Done When Criteria: A described workflow runs through the orchestrator."""
    compiler = DescribeToWorkflowCompiler()
    bridge = OrchestratorBridge()

    # Step 1: User specifies workflow in plain English
    plain_language_workflow = (
        "When a pull request is submitted, run security vulnerability scanner and code quality linter "
        "in parallel, synchronize findings at the consensus barrier, then notify the review team."
    )
    request = DescribeWorkflowRequest(
        prompt=plain_language_workflow,
        workflow_name="Automated PR Security & Quality Review",
    )

    # Step 2: Compile description into verified WorkflowGraph
    build_result = compiler.compile_workflow(request)
    assert build_result.success is True
    graph = build_result.workflow
    assert graph is not None
    assert len(graph.nodes) >= 5
    assert len(graph.edges) >= 4

    # Step 3: Run the described workflow through the Orchestrator
    report = bridge.execute_workflow(graph, "PR #42: Feature commit on branch staging")

    # Step 4: Verify execution completion
    assert report.success is True
    assert report.workflow_id == graph.workflow_id
    assert len(report.nodes_executed) == len(graph.nodes)
    assert report.parallel_branches_executed == 2
    assert "node_terminal_notify" in report.nodes_executed
    assert report.duration_ms >= 0.0
