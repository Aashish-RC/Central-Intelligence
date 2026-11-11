"""Listener translating orchestrator task completion events into notifications."""

from __future__ import annotations

from typing import Optional
from ..channels.dispatcher import ChannelDispatcher
from ..storage.inbox_store import NotificationItem


class OrchestratorListener:
    """Receives DAG runner lifecycle events and dispatches user notifications."""

    def __init__(self, dispatcher: Optional[ChannelDispatcher] = None) -> None:
        self.dispatcher = dispatcher or ChannelDispatcher()

    def on_task_finished(
        self,
        task_id: str,
        task_name: str,
        status: str,
        summary: str = "",
    ) -> NotificationItem:
        title = f"{task_name} ({status})"
        message = summary or f"Task '{task_name}' finished with status '{status}'."
        return self.dispatcher.dispatch(
            title=title,
            message=message,
            channel="inbox",
            metadata={"task_id": task_id, "task_name": task_name, "status": status},
        )

