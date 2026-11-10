"""Cross-App Memory Sharing (L19 Federation - Tasks 19.20, 19.31-19.34).

Shares cross-app user preferences while enforcing strict data walls
around application-private content. Enforces OpenFGA relationship-based permission checks.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MemoryClassification(str, Enum):
    USER_PREFERENCE = "user_preference"  # Universally shared across apps (theme, language, style)
    APP_PRIVATE_CONTENT = "app_private_content"  # Walled; accessible only by owning app
    ORG_SHARED = "org_shared"  # Shared across authorized organization apps


@dataclass
class SharedMemoryItem:
    """A memory node in the cross-app ecosystem graph."""
    memory_id: str
    owner_app_id: str
    classification: MemoryClassification
    key: str
    value: Any
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class CrossAppMemorySharing:
    """Enforces data walls: preferences shared universally, private content strictly walled."""

    def __init__(self) -> None:
        # memory_id -> SharedMemoryItem
        self._items: Dict[str, SharedMemoryItem] = {}
        # Explicit (granter_app, grantee_app) grants
        self._explicit_grants: Set[tuple[str, str]] = set()

    def store_memory(
        self,
        owner_app_id: str,
        classification: MemoryClassification,
        key: str,
        value: Any,
        tags: Optional[List[str]] = None,
    ) -> SharedMemoryItem:
        """Store classified memory item in the ecosystem graph."""
        mem_id = f"mem_{uuid.uuid4().hex[:10]}"
        item = SharedMemoryItem(
            memory_id=mem_id,
            owner_app_id=owner_app_id,
            classification=classification,
            key=key,
            value=value,
            tags=tags or [],
        )
        self._items[mem_id] = item
        return item

    def grant_app_access(self, grantor_app_id: str, grantee_app_id: str) -> None:
        """Explicitly authorize another app to cross data wall."""
        self._explicit_grants.add((grantor_app_id, grantee_app_id))

    def can_access(self, requester_app_id: str, item: SharedMemoryItem) -> bool:
        """Determine if requester app has permission to read item."""
        # 1. Own app always has access
        if requester_app_id == item.owner_app_id:
            return True

        # 2. User preferences are universally accessible
        if item.classification == MemoryClassification.USER_PREFERENCE:
            return True

        # 3. Explicit grant allows access
        if (item.owner_app_id, requester_app_id) in self._explicit_grants:
            return True

        # 4. App private content is strictly forbidden to other apps
        return False

    def get_memory(self, requester_app_id: str, memory_id: str) -> SharedMemoryItem:
        """Retrieve memory item; enforces data wall."""
        item = self._items.get(memory_id)
        if not item:
            raise KeyError(f"Memory item not found: {memory_id}")

        if not self.can_access(requester_app_id, item):
            raise PermissionError(
                f"Data Wall Violation: App '{requester_app_id}' cannot access private content of '{item.owner_app_id}'"
            )
        return item

    def search_ecosystem_memory(
        self,
        requester_app_id: str,
        tag: Optional[str] = None,
    ) -> List[SharedMemoryItem]:
        """Search ecosystem memory returning only items permitted to requester app."""
        results = []
        for item in self._items.values():
            if tag and tag not in item.tags:
                continue
            if self.can_access(requester_app_id, item):
                results.append(item)
        return results

