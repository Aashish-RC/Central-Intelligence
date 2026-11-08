"""Tier 1: Production Redis Working State with TTL-based expiration."""

import json
from typing import List, Optional
import redis

from memory.core.interfaces import BaseWorkingMemory
from memory.core.models import Turn
from memory.core.exceptions import AdapterConnectionError


class RedisWorkingMemory(BaseWorkingMemory):
    """Production Redis working memory adapter using Redis lists with session TTL."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 86400):
        self._url = redis_url
        self._ttl = ttl_seconds
        self._client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            try:
                self._client = redis.Redis.from_url(self._url, decode_responses=True)
                self._client.ping()
            except Exception as e:
                raise AdapterConnectionError(f"Failed to connect to Redis at {self._url}: {e}")
        return self._client

    def _session_key(self, session_id: str) -> str:
        return f"memory:working:{session_id}"

    def append_turn(self, turn: Turn) -> None:
        client = self._get_client()
        key = self._session_key(turn.session_id)
        payload = turn.model_dump_json()
        client.rpush(key, payload)
        client.expire(key, self._ttl)

    def get_active_window(self, session_id: str, limit: int = 10) -> List[Turn]:
        client = self._get_client()
        key = self._session_key(session_id)
        start = -limit if limit > 0 else 0
        raw_turns = client.lrange(key, start, -1)
        results: List[Turn] = []
        for raw in raw_turns:
            try:
                results.append(Turn.model_validate_json(raw))
            except Exception:
                pass
        return results

    def get_session_turns(self, session_id: str) -> List[Turn]:
        client = self._get_client()
        key = self._session_key(session_id)
        raw_turns = client.lrange(key, 0, -1)
        results: List[Turn] = []
        for raw in raw_turns:
            try:
                results.append(Turn.model_validate_json(raw))
            except Exception:
                pass
        return results

    def clear(self, session_id: str) -> None:
        client = self._get_client()
        key = self._session_key(session_id)
        client.delete(key)
