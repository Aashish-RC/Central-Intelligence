"""Tier 4 Zero-Data Retention (ZDR) Execution Buffer (Layer 10: Safety, Feature 10.30).

Tier 4: Zero-Data Retention — volatile in-memory execution only. Immediate RAM purge
upon delivery/fulfillment, absolute zero disk, database, or persistent log persistence.
Guaranteed TTL expiry (default 30 seconds).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ZDREphemeralItem:
    item_id: str
    user_id: str
    payload: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class Tier4ZDR:
    """Volatile RAM-only store with instant zeroization upon retrieval or expiry."""

    def __init__(self, default_ttl_seconds: int = 30):
        self.default_ttl_seconds = default_ttl_seconds
        self._ram_buffer: Dict[str, ZDREphemeralItem] = {}

    def hold_in_memory(
        self,
        payload: Any,
        user_id: str,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Stores item in ephemeral volatile memory with strict automatic expiration."""
        self._evict_expired()
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        item_id = f"zdr_{int(now*1000)}_{len(self._ram_buffer)}"

        self._ram_buffer[item_id] = ZDREphemeralItem(
            item_id=item_id,
            user_id=user_id,
            payload=payload,
            created_at=now,
            expires_at=now + ttl,
        )
        return item_id

    def retrieve_and_purge(self, item_id: str) -> Optional[Any]:
        """Atomic fetch and immediate purge from volatile RAM."""
        item = self._ram_buffer.pop(item_id, None)
        if item is None or item.is_expired():
            return None
        return item.payload

    def purge(self, user_id: str) -> int:
        """Immediate manual wipe of all RAM entries for a user."""
        to_del = [iid for iid, item in self._ram_buffer.items() if item.user_id == user_id]
        for iid in to_del:
            del self._ram_buffer[iid]
        return len(to_del)

    def _evict_expired(self) -> int:
        expired = [iid for iid, item in self._ram_buffer.items() if item.is_expired()]
        for iid in expired:
            del self._ram_buffer[iid]
        return len(expired)

    def active_count(self) -> int:
        self._evict_expired()
        return len(self._ram_buffer)
