"""Unit tests for SQLitePlanStore state checkpointing and persistence."""

import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from orchestrator.storage.sqlite_plan_store import SQLitePlanStore


@pytest.fixture
def store():
    return SQLitePlanStore(db_path=":memory:")


def test_save_and_retrieve_plan(store):
    planner = MultiStepPlanner()
    specs = [
        {"id": "s1", "title": "First Step", "action": "fetch", "depends_on": []},
        {"id": "s2", "title": "Second Step", "action": "parse", "depends_on": ["s1"]},
    ]
    plan = planner.create_plan("Persisted Plan", specs, project_id="proj-orchestration")
    store.save_plan(plan)

    retrieved = store.get_plan(plan.id)
    assert retrieved is not None
    assert retrieved.id == plan.id
    assert retrieved.title == "Persisted Plan"
    assert retrieved.project_id == "proj-orchestration"
    assert len(retrieved.nodes) == 2


def test_update_node_checkpoint(store):
    planner = MultiStepPlanner()
    plan = planner.create_plan("Checkpoint Plan", [{"id": "node1", "depends_on": []}])
    store.save_plan(plan)

    store.update_node(
        plan_id=plan.id,
        node_id="node1",
        status=TaskStatus.COMPLETED,
        output={"status": "all good"},
        duration_ms=45.2,
    )

    reloaded = store.get_plan(plan.id)
    n1 = reloaded.nodes["node1"]
    assert n1.status == TaskStatus.COMPLETED
    assert n1.output == {"status": "all good"}
    assert n1.duration_ms == 45.2
