"""In-memory and extensible inbox store for orchestration notifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class NotificationItem:
    """A single notification delivered to the user or system inbox."""

    title: str
    message: str
    channel: str = "inbox"
    status: str = "unread"
    id: str = field(default_factory=lambda: f"notif_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class InboxStore:
    """Stores dispatched notifications for retrieval and acknowledgement."""

    def __init__(self) -> None:
        self._items: List[NotificationItem] = []

    def add_notification(self, item: NotificationItem) -> NotificationItem:
        self._items.append(item)
        return item

    def list_notifications(self, channel: Optional[str] = None) -> List[NotificationItem]:
        if channel is None:
            return list(self._items)
        return [item for item in self._items if item.channel == channel]

    def mark_read(self, notification_id: str) -> bool:
        for item in self._items:
            if item.id == notification_id:
                item.status = "read"
                return True
        return False

    def clear(self) -> None:
        self._items.clear()

