"""Huly Project Management & Unified Docs Adapter (L19 Federation - Task 19.1).

Connects AI agents to the Huly workspace platform. Enables agents to autonomously
create issues, assign tasks to human team members or other subagents, update sprint states,
and manage collaborative knowledge docs.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    is_production,
    require_live_adapter,
)

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

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        workspace_id: str = "central-team",
        api_token: Optional[str] = None,
    ) -> None:
        self.endpoint_url = (endpoint_url or os.getenv("HULY_URL", "http://localhost:8085")).rstrip("/")
        self.workspace_id = workspace_id
        self.api_token = api_token if api_token is not None else os.getenv("HULY_API_TOKEN", "")
        self.adapter_mode = require_live_adapter(
            "huly",
            require_credentials={"api_token": self.api_token},
        )
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
        self.adapter_mode = require_live_adapter(
            "huly",
            require_credentials={"api_token": self.api_token},
        )
        if is_production() or self.adapter_mode == "live":
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(
                        f"{self.endpoint_url}/api/v1/workspaces/{self.workspace_id}/tasks",
                        json={
                            "project_id": project_id,
                            "title": title,
                            "description": description,
                            "assignee": assignee,
                            "priority": priority.value,
                            "created_by": created_by,
                            "tags": tags or [],
                        },
                        headers={"Authorization": f"Bearer {self.api_token}"},
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        task = HulyTask(
                            task_id=str(data.get("task_id") or f"HL-{uuid.uuid4().hex[:6].upper()}"),
                            project_id=project_id,
                            title=title,
                            description=description,
                            assignee=assignee,
                            status=TaskStatus(data.get("status", TaskStatus.TODO.value)),
                            priority=priority,
                            created_by=created_by,
                            tags=tags or [],
                        )
                        self._tasks[task.task_id] = task
                        return task
                    fail_closed_in_production("huly", f"Huly API returned HTTP {resp.status_code}")
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("huly", f"Huly task creation failed: {exc}", cause=exc)

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

