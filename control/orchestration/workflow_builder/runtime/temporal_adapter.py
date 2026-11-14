"""Temporal Workflow Adapter: Durable, crash-resilient workflow execution engine.

Enables multi-day workflows that survive process restarts and infrastructure crashes
by persisting execution checkpoints and event history.
Follows the orchestrator bridge pattern while integrating with Temporal / durable state replay.

Feature ID: 8.31
Repo: https://github.com/temporalio/temporal
License: MIT
"""

import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set

from ..core.interfaces import BaseOrchestratorBridge
from ..core.models import (
    WorkflowExecutionReport,
    WorkflowGraph,
    WorkflowNodeType,
)
from control.safety.production_guard import (
    fail_closed_in_production,
    require_live_adapter,
)


class TemporalWorkflowAdapter(BaseOrchestratorBridge):
    """Executes workflows durably with state checkpoints surviving process restarts."""

    def __init__(
        self,
        target_host: str = "localhost:7233",
        namespace: str = "default",
        task_queue: str = "central-workflows",
        checkpoint_dir: str = "./.temporal_checkpoints",
        _defer_prod_check: bool = False,
    ):
        self.target_host = target_host
        self.namespace = namespace
        self.task_queue = task_queue
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("temporal")
        )
        self._temporal_client: Optional[Any] = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize live Temporal client when in live mode."""
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            self._client_module = None
            return
        try:
            from temporalio.client import Client
            self._client_module = Client
        except ImportError as exc:
            fail_closed_in_production(
                "temporal",
                "temporalio package is not installed; pip install temporalio>=1.7.0",
                cause=exc,
            )

    async def _get_client(self) -> Any:
        """Connect to live Temporal server, caching the client for reuse."""
        if self._temporal_client is not None:
            return self._temporal_client
        if self._client_module is None:
            try:
                from temporalio.client import Client
                self._client_module = Client
            except ImportError as exc:
                fail_closed_in_production(
                    "temporal",
                    "temporalio package is not installed; pip install temporalio>=1.7.0",
                    cause=exc,
                )
        try:
            self._temporal_client = await self._client_module.connect(
                target_host=self.target_host,
                namespace=self.namespace,
            )
            return self._temporal_client
        except Exception as exc:
            fail_closed_in_production(
                "temporal",
                f"Failed to connect to Temporal at {self.target_host}: {exc}",
                cause=exc,
            )

    async def start_worker(self) -> None:
        """Start a long-running Temporal worker on this process.

        Call this from a dedicated worker process, NOT from request handlers.
        The worker listens on self.task_queue and executes CIDagWorkflow.
        """
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return
        try:
            from temporalio.worker import Worker
            from .temporal_workflow import CIDagWorkflow
            from .temporal_activities import execute_node

            client = await self._get_client()
            worker = Worker(
                client,
                task_queue=self.task_queue,
                workflows=[CIDagWorkflow],
                activities=[execute_node],
            )
            await worker.run()
        except Exception as exc:
            fail_closed_in_production(
                "temporal",
                f"Temporal worker failed to start: {exc}",
                cause=exc,
            )

    async def execute_workflow_live(
        self,
        graph: WorkflowGraph,
        initial_input: str = "",
    ) -> WorkflowExecutionReport:
        """Live-mode workflow execution via Temporal server."""
        from .temporal_workflow import CIDagWorkflow

        client = await self._get_client()
        graph_dict = graph.to_dict()

        workflow_id = graph.workflow_id or f"wf-{int(time.time()*1000)}"
        start_time = time.perf_counter()
        try:
            handle = await client.start_workflow(
                CIDagWorkflow.run,
                graph_dict,
                initial_input,
                id=workflow_id,
                task_queue=self.task_queue,
            )
            result = await handle.result()
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return WorkflowExecutionReport(
                workflow_id=workflow_id,
                nodes_executed=result.get("nodes_executed", []),
                parallel_branches_executed=0,
                success=result.get("success", True),
                duration_ms=round(duration_ms, 2),
                outputs=result.get("outputs", {}),
            )
        except Exception as exc:
            fail_closed_in_production(
                "temporal",
                f"Workflow {workflow_id} failed: {exc}",
                cause=exc,
            )

    def _get_checkpoint_path(self, workflow_id: str) -> Path:
        return self.checkpoint_dir / f"{workflow_id}.json"

    def save_checkpoint(
        self,
        workflow_id: str,
        completed_nodes: Set[str],
        outputs: Dict[str, str],
        step_count: int,
    ) -> None:
        """Persist workflow state to disk checkpoint surviving process death."""
        data = {
            "workflow_id": workflow_id,
            "completed_nodes": list(completed_nodes),
            "outputs": outputs,
            "step_count": step_count,
            "updated_at": time.time(),
        }
        with open(self._get_checkpoint_path(workflow_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_checkpoint(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load existing checkpoint state if process was restarted mid-execution."""
        path = self._get_checkpoint_path(workflow_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def clear_checkpoint(self, workflow_id: str) -> None:
        """Remove checkpoint after successful workflow completion."""
        path = self._get_checkpoint_path(workflow_id)
        if path.exists():
            path.unlink(missing_ok=True)

    def execute_workflow(
        self,
        graph: WorkflowGraph,
        initial_input: str = "",
        resume: bool = True,
        fail_at_step: Optional[int] = None,
    ) -> WorkflowExecutionReport:
        """Executes workflow with durability guarantees.
        
        If killed or failed previously, execution seamlessly resumes from
        the last recorded checkpoint without repeating already completed steps.
        """
        if self.adapter_mode == "live" and os.getenv("CI_TEST_MODE") != "1":
            import asyncio
            return asyncio.run(self.execute_workflow_live(graph, initial_input))

        start_time = time.perf_counter()
        workflow_id = graph.workflow_id
        executed_nodes: List[str] = []
        outputs: Dict[str, str] = {}
        completed: Set[str] = set()
        parallel_branches = 0
        step_counter = 0

        # Check for prior checkpoint (resuming after simulated crash/restart)
        if resume:
            checkpoint = self.load_checkpoint(workflow_id)
            if checkpoint:
                completed = set(checkpoint.get("completed_nodes", []))
                outputs = checkpoint.get("outputs", {})
                executed_nodes = list(completed)
                step_counter = checkpoint.get("step_count", len(completed))

        # Topological candidate resolution
        ready_nodes = [
            nid
            for nid, node in graph.nodes.items()
            if nid not in completed and all(dep in completed for dep in node.upstream_dependencies)
        ]

        while ready_nodes:
            current_id = ready_nodes.pop(0)
            node = graph.nodes[current_id]
            step_counter += 1

            # Simulated process crash for resilience verification
            if fail_at_step is not None and step_counter == fail_at_step:
                self.save_checkpoint(
                    workflow_id=workflow_id,
                    completed_nodes=completed,
                    outputs=outputs,
                    step_count=step_counter - 1,
                )
                raise ProcessLookupError(
                    f"[Temporal Replay] Simulated process crash at step {step_counter} on node '{current_id}'"
                )

            # Node execution
            executed_nodes.append(current_id)
            if node.node_type == WorkflowNodeType.PARALLEL_FANOUT:
                parallel_branches += 2
            outputs[current_id] = f"Completed action '{node.action_name}' on {node.label}"
            completed.add(current_id)

            # Checkpoint progress after each state transition
            self.save_checkpoint(
                workflow_id=workflow_id,
                completed_nodes=completed,
                outputs=outputs,
                step_count=step_counter,
            )

            # Discover next ready nodes
            for nid, candidate in graph.nodes.items():
                if nid not in completed and nid not in ready_nodes:
                    if all(dep in completed for dep in candidate.upstream_dependencies):
                        ready_nodes.append(nid)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return WorkflowExecutionReport(
            workflow_id=workflow_id,
            nodes_executed=executed_nodes,
            parallel_branches_executed=parallel_branches,
            success=True,
            duration_ms=round(duration_ms, 2),
            outputs=outputs,
        )
