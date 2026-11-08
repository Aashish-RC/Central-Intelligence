"""Tests for DescribeToWorkflowCompiler."""

import pytest
from workflow_builder.core.models import (
    DescribeWorkflowRequest,
    WorkflowNodeType,
)
from workflow_builder.compiler.describe_to_workflow import DescribeToWorkflowCompiler


@pytest.fixture
def compiler():
    return DescribeToWorkflowCompiler()


def test_compile_short_prompt_rejected(compiler):
    req = DescribeWorkflowRequest(prompt="no")
    result = compiler.compile_workflow(req)
    assert result.success is False
    assert len(result.validation_errors) > 0


def test_compile_parallel_workflow(compiler):
    prompt = "When code is pushed, run security scan and linter in parallel, then notify team."
    req = DescribeWorkflowRequest(prompt=prompt, workflow_name="CI Parallel Pipeline")
    result = compiler.compile_workflow(req)

    assert result.success is True
    graph = result.workflow
    assert graph is not None
    assert graph.name == "CI Parallel Pipeline"

    # Verify parallel nodes exist
    types = [n.node_type for n in graph.nodes.values()]
    assert WorkflowNodeType.TRIGGER in types
    assert WorkflowNodeType.PARALLEL_FANOUT in types
    assert WorkflowNodeType.AGENT_STEP in types
    assert WorkflowNodeType.AGGREGATE_FANIN in types
    assert WorkflowNodeType.TERMINATION in types
    assert len(graph.edges) >= 4


def test_compile_sequential_workflow(compiler):
    prompt = "Read repository documentation and summarize findings into a report."
    req = DescribeWorkflowRequest(prompt=prompt, workflow_name="Doc Summarizer")
    result = compiler.compile_workflow(req)

    assert result.success is True
    graph = result.workflow
    assert graph is not None
    types = [n.node_type for n in graph.nodes.values()]
    assert WorkflowNodeType.PARALLEL_FANOUT not in types
    assert WorkflowNodeType.AGENT_STEP in types
