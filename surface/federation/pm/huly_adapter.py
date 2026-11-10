"""Huly Project Management & Unified Docs Adapter (L19 Federation - Task 19.1).

Connects AI agents to the Huly workspace platform. Enables agents to autonomously
create issues, assign tasks to human team members or other subagents, update sprint states,
and manage collaborative knowledge docs.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


@dataclass
class HulyTask:
    """A task/issue item in Huly workspace."""
    task_id: str
    project_id: str
    title: str
    description: str
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    created_by: str = "agent"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)


@dataclass
class HulyDoc:
    """A collaborative rich document in Huly."""
    doc_id: str
    title: str
    content_markdown: str
    author: str = "agent"
    created_at: float = field(default_factory=time.time)


class HulyAdapter:
    """Adapter for Huly project management and documents."""

    def __init__(self, endpoint_url: str = "http://localhost:8085", workspace_id: str = "central-team") -> None:
        self.endpoint_url = endpoint_url
        self.workspace_id = workspace_id
        self._tasks: Dict[str, HulyTask] = {}
        self._docs: Dict[str, HulyDoc] = {}

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str,
        assignee: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        created_by: str = "autonomous_agent",
        tags: Optional[List[str]] = None,
    ) -> HulyTask:
        """Create a new task in Huly."""
        task_id = f"HL-{uuid.uuid4().hex[:6].upper()}"
        task = HulyTask(
            task_id=task_id,
            project_id=project_id,
            title=title,
            description=description,
            assignee=assignee,
            status=TaskStatus.TODO,
            priority=priority,
            created_by=created_by,
            tags=tags or [],
        )
        self._tasks[task_id] = task
        logger.info("Created Huly task %s in project %s (assignee: %s)", task_id, project_id, assignee)
        return task

    def assign_task(self, task_id: str, assignee: str) -> HulyTask:
        """Assign an existing task to team member or agent."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.assignee = assignee
        task.updated_at = time.time()
        logger.info("Assigned Huly task %s to %s", task_id, assignee)
        return task

    def update_status(self, task_id: str, status: TaskStatus) -> HulyTask:
        """Advance task lifecycle status."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = status
        task.updated_at = time.time()
        return task

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[HulyTask]:
        """Query tasks matching filters."""
        results = []
        for task in self._tasks.values():
            if project_id and task.project_id != project_id:
                continue
            if assignee and task.assignee != assignee:
                continue
            if status and task.status != status:
                continue
            results.append(task)
        return results

    def create_doc(self, title: str, content: str, author: str = "agent") -> HulyDoc:
        """Create document in Huly knowledge base."""
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        doc = HulyDoc(
            doc_id=doc_id,
            title=title,
            content_markdown=content,
            author=author,
        )
        self._docs[doc_id] = doc
        return doc

    def get_doc(self, doc_id: str) -> Optional[HulyDoc]:
        return self._docs.get(doc_id)

