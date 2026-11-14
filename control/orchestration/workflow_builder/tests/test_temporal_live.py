"""Live integration tests for Temporal workflow adapter (Layer 8).

Executed against a live Temporal server (gRPC at localhost:7233).
Skipped in hermetic/CI test mode unless TEMPORAL_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
import pytest

from control.orchestration.workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from control.orchestration.workflow_builder.runtime.temporal_adapter import (
    TemporalWorkflowAdapter,
)
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

TEMPORAL_LIVE_URL = os.getenv("TEMPORAL_LIVE_URL")


def _build_five_node_graph(wf_id: str) -> WorkflowGraph:
    nodes = {
        f"step_{i}": WorkflowNode(
            node_id=f"step_{i}",
            node_type=WorkflowNodeType.AGENT_STEP if i > 0 else WorkflowNodeType.TRIGGER,
            label=f"Step {i}",
            action_name=f"action_{i}",
            upstream_dependencies=[f"step_{i-1}"] if i > 0 else [],
        )
        for i in range(5)
    }
    edges = [
        WorkflowEdge(source_node_id=f"step_{i}", target_node_id=f"step_{i+1}")
        for i in range(4)
    ]
    return WorkflowGraph(
        workflow_id=wf_id,
        name="Five Node Live Workflow",
        description="Live Temporal durability test graph",
        nodes=nodes,
        edges=edges,
    )


def _start_worker_process(host: str, queue: str) -> subprocess.Popen:
    """Spawns a separate Python process running Temporal worker."""
    worker_code = f"""
import asyncio
from control.orchestration.workflow_builder.runtime.temporal_adapter import TemporalWorkflowAdapter
adapter = TemporalWorkflowAdapter(target_host="{host}", task_queue="{queue}", _defer_prod_check=True)
adapter.adapter_mode = "live"
asyncio.run(adapter.start_worker())
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", worker_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2.0)
    return proc


@pytest.mark.asyncio
async def test_workflow_persists_across_worker_restart():
    """Start worker subprocess, start workflow, kill worker, restart worker, verify completion."""
    if not TEMPORAL_LIVE_URL:
        pytest.skip("TEMPORAL_LIVE_URL not set; skipping live Temporal tests")

    queue = f"test-queue-{uuid.uuid4().hex[:8]}"
    wf_id = f"wf-durability-{uuid.uuid4().hex[:8]}"
    graph = _build_five_node_graph(wf_id)

    worker = _start_worker_process(TEMPORAL_LIVE_URL, queue)
    adapter = TemporalWorkflowAdapter(
        target_host=TEMPORAL_LIVE_URL,
        task_queue=queue,
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    try:
        client = await adapter._get_client()
        from control.orchestration.workflow_builder.runtime.temporal_workflow import CIDagWorkflow
        handle = await client.start_workflow(
            CIDagWorkflow.run,
            graph.to_dict(),
            id=wf_id,
            task_queue=queue,
        )

        # Kill the worker midway
        time.sleep(0.5)
        worker.terminate()
        worker.wait(timeout=5.0)

        # Restart worker
        new_worker = _start_worker_process(TEMPORAL_LIVE_URL, queue)
        try:
            result = await handle.result()
            assert result["success"] is True
            assert len(result["nodes_executed"]) == 5
            assert "step_4" in result["outputs"]
        finally:
            new_worker.terminate()
            new_worker.wait(timeout=5.0)
    finally:
        if worker.poll() is None:
            worker.terminate()


@pytest.mark.asyncio
async def test_workflow_history_visible_in_temporal_ui():
    """Workflow execution status and history are registered on the live Temporal server."""
    if not TEMPORAL_LIVE_URL:
        pytest.skip("TEMPORAL_LIVE_URL not set; skipping live Temporal tests")

    queue = f"test-queue-{uuid.uuid4().hex[:8]}"
    wf_id = f"wf-history-{uuid.uuid4().hex[:8]}"
    graph = _build_five_node_graph(wf_id)

    worker = _start_worker_process(TEMPORAL_LIVE_URL, queue)
    adapter = TemporalWorkflowAdapter(
        target_host=TEMPORAL_LIVE_URL,
        task_queue=queue,
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    try:
        client = await adapter._get_client()
        from control.orchestration.workflow_builder.runtime.temporal_workflow import CIDagWorkflow
        handle = await client.start_workflow(
            CIDagWorkflow.run,
            graph.to_dict(),
            id=wf_id,
            task_queue=queue,
        )
        desc = await handle.describe()
        assert desc.status is not None
        result = await handle.result()
        assert result["success"] is True
    finally:
        worker.terminate()
        worker.wait(timeout=5.0)


def test_temporal_down_fails_closed(monkeypatch):
    """When ADAPTER_MODE=live and Temporal is unreachable, fail closed with ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = TemporalWorkflowAdapter(
        target_host="127.0.0.1:59999",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    graph = _build_five_node_graph("wf-down-test")
    with pytest.raises(ProductionSafetyError):
        adapter.execute_workflow(graph)

