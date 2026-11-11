"""Dragonfly Cache Adapter (L15 Data & Messaging - Task 15.2).

Dragonfly is a high-throughput, multi-threaded drop-in Redis replacement that
delivers up to 25x faster performance for in-memory caching and real-time pub/sub.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    is_production,
    require_live_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class DragonflyConfig:
    """Configuration options for Dragonfly connection."""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    default_ttl_seconds: Optional[int] = 3600
    socket_timeout: float = 2.0
    use_mock: bool = False


class DragonflyAdapter:
    """Adapter for Dragonfly cache and pub/sub.

    Supports key-value get/set/del/mget/mset, TTL expirations, and pub/sub channels.
    Includes in-memory simulation for deterministic testing and offline operation.
    """

    def __init__(self, config: Optional[DragonflyConfig] = None) -> None:
        self.config = config or DragonflyConfig()
        self._is_connected: bool = False
        self._client: Any = None
        self.adapter_mode = require_live_adapter("dragonfly")

        if is_production() and self.config.use_mock:
            raise ProductionSafetyError(
                "Dragonfly adapter cannot run with use_mock=True in production."
            )

        # In-memory storage for mock/fallback
        self._store: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}
        self._subscribers: Dict[str, Set[Callable[[str, Any], None]]] = {}

        if not self.config.use_mock:
            self._init_client()

    def _init_client(self) -> None:
        """Attempt connecting to real Dragonfly instance via redis client if available."""
        try:
            import redis  # type: ignore

            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                socket_timeout=self.config.socket_timeout,
                decode_responses=True,
            )
            self._client.ping()
            self._is_connected = True
            logger.info("Connected to Dragonfly at %s:%s", self.config.host, self.config.port)
        except Exception as exc:
            self._is_connected = False
            self._client = None
            fail_closed_in_production(
                "dragonfly",
                f"Could not connect to live Dragonfly at {self.config.host}:{self.config.port}: {exc}",
                cause=exc,
            )
            logger.warning(
                "Could not connect to live Dragonfly at %s:%s (%s). Falling back to in-memory mode.",
                self.config.host,
                self.config.port,
                exc,
            )

    @property
    def is_connected(self) -> bool:
        """Return True if connected to live Dragonfly backend."""
        return self._is_connected

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Store key-value pair with optional TTL."""
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.config.default_ttl_seconds

        if self._is_connected and self._client:
            try:
                serialized = json.dumps(value) if not isinstance(value, (str, int, float, bytes)) else value
                if effective_ttl:
                    return bool(self._client.setex(key, effective_ttl, serialized))
                return bool(self._client.set(key, serialized))
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly set error on key {key}: {exc}", cause=exc)
                logger.error("Dragonfly set error on key %s: %s", key, exc)

        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for set()")
        # Fallback / mock implementation
        self._store[key] = value
        if effective_ttl:
            self._expires[key] = time.time() + effective_ttl
        elif key in self._expires:
            del self._expires[key]
        return True

    def get(self, key: str) -> Optional[Any]:
        """Retrieve key value if present and unexpired."""
        if self._is_connected and self._client:
            try:
                raw = self._client.get(key)
                if raw is None:
                    return None
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly get error on key {key}: {exc}", cause=exc)
                logger.error("Dragonfly get error on key %s: %s", key, exc)

        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for get()")
        # Mock implementation with TTL check
        if key in self._expires and time.time() > self._expires[key]:
            self.delete(key)
            return None
        return self._store.get(key)

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        deleted_count = 0
        if self._is_connected and self._client:
            try:
                return int(self._client.delete(*keys))
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly delete error: {exc}", cause=exc)
                logger.error("Dragonfly delete error: %s", exc)

        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for delete()")
        for k in keys:
            if k in self._store:
                del self._store[k]
                deleted_count += 1
            if k in self._expires:
                del self._expires[k]
        return deleted_count

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        if self._is_connected and self._client:
            try:
                return bool(self._client.exists(key))
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly exists error: {exc}", cause=exc)
                logger.error("Dragonfly exists error: %s", exc)

        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for exists()")
        if key in self._expires and time.time() > self._expires[key]:
            self.delete(key)
            return False
        return key in self._store

    def mset(self, mapping: Dict[str, Any], ttl_seconds: Optional[int] = None) -> bool:
        """Batch set multiple key-value pairs."""
        for k, v in mapping.items():
            self.set(k, v, ttl_seconds=ttl_seconds)
        return True

    def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """Batch retrieve multiple keys."""
        return [self.get(k) for k in keys]

    def publish(self, channel: str, message: Any) -> int:
        """Publish message to a channel, returns number of recipients."""
        payload = message if isinstance(message, str) else json.dumps(message)

        if self._is_connected and self._client:
            try:
                return int(self._client.publish(channel, payload))
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly publish error on channel {channel}: {exc}", cause=exc)
                logger.error("Dragonfly publish error on channel %s: %s", channel, exc)

        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for publish()")
        subscribers = self._subscribers.get(channel, set())
        for callback in list(subscribers):
            try:
                callback(channel, message)
            except Exception as exc:
                logger.exception("Error in subscriber callback for channel %s: %s", channel, exc)
        return len(subscribers)

    def subscribe(self, channel: str, callback: Callable[[str, Any], None]) -> None:
        """Subscribe callback to a channel."""
        if channel not in self._subscribers:
            self._subscribers[channel] = set()
        self._subscribers[channel].add(callback)

    def unsubscribe(self, channel: str, callback: Optional[Callable[[str, Any], None]] = None) -> None:
        """Unsubscribe callback or remove entire channel."""
        if channel in self._subscribers:
            if callback:
                self._subscribers[channel].discard(callback)
            else:
                del self._subscribers[channel]

    def flushdb(self) -> bool:
        """Clear all stored keys."""
        if self._is_connected and self._client:
            try:
                self._client.flushdb()
                return True
            except Exception as exc:
                fail_closed_in_production("dragonfly", f"Dragonfly flushdb error: {exc}", cause=exc)
                logger.error("Dragonfly flushdb error: %s", exc)
        fail_closed_in_production("dragonfly", "No active live Dragonfly connection for flushdb()")
        self._store.clear()
        self._expires.clear()
        return True

