"""Unit tests for HulyAdapter (Task 19.1)."""

import pytest
from surface.federation.pm.huly_adapter import (
    HulyAdapter,
    TaskPriority,
    TaskStatus,
)


@pytest.fixture
def huly():
    return HulyAdapter()


def test_agent_creates_and_assigns_task_in_huly(huly: HulyAdapter):
    """Acceptance test: Agent can create a task in Huly and assign it."""
    project_id = "PRJ_CORE_PLATFORM"

    # 1. Agent creates task
    task = huly.create_task(
        project_id=project_id,
        title="Audit Postgres RLS policy configurations",
        description="Verify tenant isolation on all central tables before Wave D release.",
        priority=TaskPriority.HIGH,
        created_by="security_evaluator_agent",
    )

    assert task.task_id.startswith("HL-")
    assert task.status == TaskStatus.TODO
    assert task.assignee is None
    assert task.created_by == "security_evaluator_agent"

    # 2. Agent assigns task to a team member
    assigned = huly.assign_task(task.task_id, assignee="alice_lead_dev")
    assert assigned.assignee == "alice_lead_dev"

    # 3. Update status
    updated = huly.update_status(task.task_id, TaskStatus.IN_PROGRESS)
    assert updated.status == TaskStatus.IN_PROGRESS

    # 4. Query tasks by assignee
    alice_tasks = huly.list_tasks(assignee="alice_lead_dev")
    assert len(alice_tasks) == 1
    assert alice_tasks[0].task_id == task.task_id


def test_create_and_read_huly_doc(huly: HulyAdapter):
    """Agent creates unified collaborative documentation in Huly."""
    doc = huly.create_doc(
        title="L19 Federation Protocol Architecture",
        content="# Federation Overview\nFederated brains communicate via cryptographic envelopes.",
        author="agent_architect",
    )
    assert doc.doc_id.startswith("doc_")

    fetched = huly.get_doc(doc.doc_id)
    assert fetched is not None
    assert fetched.title == "L19 Federation Protocol Architecture"
    assert "cryptographic envelopes" in fetched.content_markdown
