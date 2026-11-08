"""Tier 1: Working State Cache with Optional WAL (Write-Ahead Logging)."""

from __future__ import annotations
import json
import os
import time
from typing import Any, Dict, List, Optional


class WorkingMemoryTier:
    """Fast in-memory session scratchpad with WAL support and Redis fallback."""

    def __init__(self, wal_dir: Optional[str] = None, redis_client: Optional[Any] = None):
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self.wal_dir = wal_dir
        self.redis = redis_client

        if self.wal_dir:
            os.makedirs(self.wal_dir, exist_ok=True)

    def append_turn(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Append turn to active working memory session."""
        turn = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }

        if session_id not in self._cache:
            self._cache[session_id] = []
        self._cache[session_id].append(turn)

        # Write to WAL if configured
        if self.wal_dir:
            wal_file = os.path.join(self.wal_dir, f"{session_id}.wal")
            with open(wal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(turn) + "\n")

        # Sync to Redis if connected
        if self.redis:
            try:
                self.redis.rpush(f"session:{session_id}:turns", json.dumps(turn))
            except Exception:
                pass

        return turn

    def get_recent_turns(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve the most recent turns for a session."""
        turns = self._cache.get(session_id, [])
        return turns[-limit:]

    def clear_session(self, session_id: str) -> None:
        """Clear session working memory."""
        if session_id in self._cache:
            del self._cache[session_id]
        if self.wal_dir:
            wal_file = os.path.join(self.wal_dir, f"{session_id}.wal")
            if os.path.exists(wal_file):
                os.remove(wal_file)
        if self.redis:
            try:
                self.redis.delete(f"session:{session_id}:turns")
            except Exception:
                pass
