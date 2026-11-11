"""Tests for BackupManager (L15 Feature 15.37)."""

from __future__ import annotations

from platform_infra.data.backup.backup_manager import BackupManager


def test_point_in_time_backup_and_restore() -> None:
    fact_store = {"u1": "v1"}
    vector_store = {"docs": ["a"]}

    mgr = BackupManager()
    mgr.register_store("facts", lambda: fact_store, lambda data: (fact_store.clear(), fact_store.update(data)))
    mgr.register_store("vectors", lambda: vector_store, lambda data: (vector_store.clear(), vector_store.update(data)))

    mgr.create_backup(label="yesterday", timestamp=1000.0)
    fact_store["u1"] = "corrupted"
    vector_store["docs"].append("bad")
    mgr.create_backup(label="after-bug", timestamp=2000.0)

    restored = mgr.restore_point_in_time(1500.0)
    assert restored.label == "yesterday"
    assert fact_store == {"u1": "v1"}
    assert vector_store == {"docs": ["a"]}

