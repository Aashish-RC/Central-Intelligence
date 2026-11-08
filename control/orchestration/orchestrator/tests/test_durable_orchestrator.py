"""Unit tests for durable orchestrator checkpointing and resume capability."""

from orchestrator.core.models import TaskStatus
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from orchestrator.storage.sqlite_plan_store import SQLitePlanStore


def test_durable_orchestrator_resume():
    store = SQLitePlanStore(db_path=":memory:")
    runner = ParallelDAGRunner(store=store)
    planner = MultiStepPlanner()

    specs = [
        {"id": "step_1", "title": "Extract Data", "action": "noop", "depends_on": []},
        {"id": "step_2", "title": "Transform Data", "action": "noop", "depends_on": ["step_1"]},
        {"id": "step_3", "title": "Load Data", "action": "noop", "depends_on": ["step_2"]},
    ]
    plan = planner.create_plan("ETL Pipeline", specs, project_id="proj-resilience")
    store.save_plan(plan)

    # Simulate that step_1 already completed before a crash/interrupt
    store.update_node(
        plan_id=plan.id,
        node_id="step_1",
        status=TaskStatus.COMPLETED,
        output={"extracted_records": 42},
        duration_ms=12.5,
    )
    store.update_plan_status(plan.id, TaskStatus.RUNNING)

    # Resume the interrupted plan
    report = runner.resume_plan(plan.id)

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 3
    assert len(report.node_results) == 3
    # Verify step_1 reused checkpointed output
    assert report.node_results["step_1"].output == {"extracted_records": 42}
    assert report.node_results["step_1"].status == TaskStatus.COMPLETED
    # Verify subsequent steps completed
    assert report.node_results["step_2"].status == TaskStatus.COMPLETED
    assert report.node_results["step_3"].status == TaskStatus.COMPLETED
