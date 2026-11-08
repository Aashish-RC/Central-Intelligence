"""Unit tests for ParallelDAGRunner: parallel fan-out and fan-in synchronization."""

import time
import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.planner.multi_step_planner import MultiStepPlanner


@pytest.fixture
def runner():
    return ParallelDAGRunner()


def test_parallel_fanout_execution(runner):
    planner = MultiStepPlanner()
    # 3 independent parallel worker tasks that sleep 0.1s each
    # Total time should be ~0.1s in parallel rather than ~0.3s sequential
    runner.register_handler("worker", lambda node, ctx: time.sleep(0.1) or f"Output of {node.id}")
    runner.register_handler(
        "aggregator",
        lambda node, ctx: f"Aggregated: {ctx.get('w1')} + {ctx.get('w2')} + {ctx.get('w3')}",
    )

    specs = [
        {"id": "w1", "action": "worker", "depends_on": []},
        {"id": "w2", "action": "worker", "depends_on": []},
        {"id": "w3", "action": "worker", "depends_on": []},
        {"id": "agg", "action": "aggregator", "depends_on": ["w1", "w2", "w3"]},
    ]

    plan = planner.create_plan("Fan-Out Fan-In Demo", specs, max_concurrency=4)
    start = time.perf_counter()
    report = runner.run_plan(plan)
    elapsed = time.perf_counter() - start

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 4
    assert report.failed_nodes == 0
    # Elapsed should be well under sequential sum (0.1s * 3 = 0.3s)
    assert elapsed < 0.25
    assert "Aggregated: Output of w1 + Output of w2 + Output of w3" in report.node_results["agg"].output
