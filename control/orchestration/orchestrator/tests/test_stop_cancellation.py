"""Unit tests for Cooperative Cancellation: A parallel task runs and can be stopped."""

import time
import threading
import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.engine.cancellation import CancellationToken
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.planner.multi_step_planner import MultiStepPlanner


@pytest.fixture
def runner():
    return ParallelDAGRunner()


def test_parallel_task_runs_and_can_be_stopped(runner):
    """Core verification: A parallel task runs and can be stopped mid-execution."""
    token = CancellationToken()

    def long_worker(node, ctx):
        for _ in range(10):
            if token.is_cancelled:
                break
            time.sleep(0.05)
        return f"Worker {node.id} done"

    runner.register_handler("long_task", long_worker)

    planner = MultiStepPlanner()
    specs = [
        {"id": "task1", "action": "long_task", "depends_on": []},
        {"id": "task2", "action": "long_task", "depends_on": []},
        {"id": "downstream1", "action": "long_task", "depends_on": ["task1"]},
        {"id": "downstream2", "action": "long_task", "depends_on": ["task2"]},
    ]
    plan = planner.create_plan("Cancellable Parallel Plan", specs, max_concurrency=4)

    # Trigger cancellation after 50ms in a background timer
    def stop_later():
        time.sleep(0.05)
        token.cancel("User pressed stop")

    t = threading.Thread(target=stop_later)
    t.start()

    report = runner.run_plan(plan, cancellation_token=token)
    t.join()

    # The plan must be cancelled and downstream tasks must be marked CANCELLED
    assert report.status == TaskStatus.CANCELLED
    assert report.cancelled_nodes >= 2
    assert plan.status == TaskStatus.CANCELLED
    assert report.node_results["downstream1"].status == TaskStatus.CANCELLED
    assert report.node_results["downstream2"].status == TaskStatus.CANCELLED


def test_pre_cancelled_token(runner):
    token = CancellationToken()
    token.cancel("Immediate halt")

    planner = MultiStepPlanner()
    plan = planner.create_plan("Pre-halt Plan", [{"id": "a", "depends_on": []}])
    report = runner.run_plan(plan, cancellation_token=token)

    assert report.status == TaskStatus.CANCELLED
    assert report.cancelled_nodes == 1
    assert report.completed_nodes == 0
