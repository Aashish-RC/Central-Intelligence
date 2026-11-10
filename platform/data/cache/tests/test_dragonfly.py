"""Unit tests for DragonflyAdapter (Task 15.2)."""

import time
import pytest
from platform.data.cache.dragonfly_adapter import DragonflyAdapter, DragonflyConfig


@pytest.fixture
def cache():
    """Create in-memory Dragonfly test instance."""
    config = DragonflyConfig(use_mock=True, default_ttl_seconds=60)
    adapter = DragonflyAdapter(config=config)
    yield adapter
    adapter.flushdb()


def test_set_and_get_keys(cache: DragonflyAdapter):
    """Test basic key-value operations with primitives and complex JSON types."""
    assert cache.set("user:101:name", "Alice")
    assert cache.get("user:101:name") == "Alice"

    payload = {"role": "admin", "permissions": ["read", "write", "execute"]}
    assert cache.set("user:101:meta", payload)
    assert cache.get("user:101:meta") == payload

    assert cache.get("nonexistent_key") is None


def test_ttl_expiration(cache: DragonflyAdapter):
    """Test that keys expire when TTL is exceeded."""
    cache.set("ephemeral_key", "temporary_value", ttl_seconds=1)
    assert cache.get("ephemeral_key") == "temporary_value"
    assert cache.exists("ephemeral_key") is True

    # Fast forward expiration manually in mock store
    cache._expires["ephemeral_key"] = time.time() - 1
    assert cache.get("ephemeral_key") is None
    assert cache.exists("ephemeral_key") is False


def test_batch_operations(cache: DragonflyAdapter):
    """Test mset, mget, and multi-key delete."""
    items = {
        "device:1": "phone",
        "device:2": "laptop",
        "device:3": "tablet",
    }
    assert cache.mset(items)

    values = cache.mget(["device:1", "device:2", "device:3", "device:4"])
    assert values == ["phone", "laptop", "tablet", None]

    deleted = cache.delete("device:1", "device:3")
    assert deleted == 2
    assert cache.get("device:1") is None
    assert cache.get("device:2") == "laptop"
    assert cache.get("device:3") is None


def test_publish_subscribe(cache: DragonflyAdapter):
    """Test pub/sub event delivery."""
    received = []

    def on_event(channel: str, message: dict):
        received.append((channel, message))

    cache.subscribe("events.system", on_event)

    recipients = cache.publish("events.system", {"type": "heartbeat", "seq": 1})
    assert recipients == 1
    assert len(received) == 1
    assert received[0] == ("events.system", {"type": "heartbeat", "seq": 1})

    # Unsubscribe
    cache.unsubscribe("events.system", on_event)
    recipients_after = cache.publish("events.system", {"type": "heartbeat", "seq": 2})
    assert recipients_after == 0
    assert len(received) == 1


def test_flushdb(cache: DragonflyAdapter):
    """Test flushdb clears state."""
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    assert cache.exists("k1")
    assert cache.exists("k2")

    cache.flushdb()
    assert cache.get("k1") is None
    assert cache.get("k2") is None
