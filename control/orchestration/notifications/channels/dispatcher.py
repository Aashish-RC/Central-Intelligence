"""Dispatches notifications to configured channels and inbox storage."""

from __future__ import annotations

from typing import Any, Dict, Optional
from ..storage.inbox_store import InboxStore, NotificationItem


class ChannelDispatcher:
    """Routes notification payloads to inbox storage and registered channel sinks."""

    def __init__(self, inbox_store: Optional[InboxStore] = None) -> None:
        self.inbox_store = inbox_store or InboxStore()

    def dispatch(
        self,
        title: str,
        message: str,
        channel: str = "inbox",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationItem:
        item = NotificationItem(
            title=title,
            message=message,
            channel=channel,
            metadata=metadata or {},
        )
        return self.inbox_store.add_notification(item)

