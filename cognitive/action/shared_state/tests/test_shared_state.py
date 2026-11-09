"""Unit tests for Concurrency & Lock Manager and Shared Scratchpad (Features 5.44, 5.45, 8.49)."""

import time
import pytest
from cognitive.action.shared_state.lock_manager import (
    DistributedLockManager,
    LockAcquisitionError,
    LockMode,
)
from cognitive.action.shared_state.scratchpad import (
    SharedScratchpad,
    ScratchpadEntry,
)


@pytest.fixture
def lock_mgr():
    return DistributedLockManager(default_ttl_seconds=5.0)


@pytest.fixture
def scratchpad(lock_mgr):
    return SharedScratchpad(namespace="test_space", lock_manager=lock_mgr)


def test_exclusive_lock_mutual_exclusion(lock_mgr):
    # Agent 1 acquires exclusive lock
    lease1 = lock_mgr.acquire("file_main.py", owner="agent_coder_1", mode=LockMode.EXCLUSIVE)
    assert lease1 is not None
    assert lock_mgr.is_locked("file_main.py")
    assert lock_mgr.get_owner("file_main.py") == "agent_coder_1"

    # Agent 2 fails to acquire within timeout
    with pytest.raises(LockAcquisitionError):
        lock_mgr.acquire(
            "file_main.py",
            owner="agent_coder_2",
            mode=LockMode.EXCLUSIVE,
            timeout=0.1,
        )

    # Agent 1 releases lock
    assert lock_mgr.release("file_main.py", owner="agent_coder_1") is True
    assert not lock_mgr.is_locked("file_main.py")

    # Agent 2 can now acquire lock
    lease2 = lock_mgr.acquire("file_main.py", owner="agent_coder_2", mode=LockMode.EXCLUSIVE)
    assert lease2.owner == "agent_coder_2"
    lock_mgr.release("file_main.py", owner="agent_coder_2")


def test_lock_reentrancy(lock_mgr):
    # Agent acquires twice
    lease = lock_mgr.acquire("db_conn", owner="agent_lead")
    assert lease.reentrancy_count == 1

    lease_reenter = lock_mgr.acquire("db_conn", owner="agent_lead")
    assert lease_reenter.reentrancy_count == 2

    # First release leaves it locked
    assert lock_mgr.release("db_conn", owner="agent_lead") is True
    assert lock_mgr.is_locked("db_conn") is True

    # Second release frees it
    assert lock_mgr.release("db_conn", owner="agent_lead") is True
    assert lock_mgr.is_locked("db_conn") is False


def test_shared_reader_locks(lock_mgr):
    # Multiple agents acquire shared read locks
    l1 = lock_mgr.acquire("schema.json", owner="reader_1", mode=LockMode.SHARED)
    l2 = lock_mgr.acquire("schema.json", owner="reader_2", mode=LockMode.SHARED)
    assert l1 is not None and l2 is not None

    # Writer cannot acquire exclusive lock while readers hold shared lock
    with pytest.raises(LockAcquisitionError):
        lock_mgr.acquire("schema.json", owner="writer_1", mode=LockMode.EXCLUSIVE, timeout=0.1)

    # Both readers release
    lock_mgr.release("schema.json", owner="reader_1")
    lock_mgr.release("schema.json", owner="reader_2")

    # Writer can now acquire exclusive lock
    writer_lease = lock_mgr.acquire("schema.json", owner="writer_1", mode=LockMode.EXCLUSIVE)
    assert writer_lease.owner == "writer_1"
    lock_mgr.release("schema.json", owner="writer_1")


def test_lock_lease_auto_expiration(lock_mgr):
    # Short TTL lease
    lock_mgr.acquire("temp_key", owner="agent_crashed", ttl_seconds=0.1)
    assert lock_mgr.is_locked("temp_key") is True

    # Wait for TTL expiration
    time.sleep(0.15)
    assert lock_mgr.is_locked("temp_key") is False

    # New agent acquires expired resource cleanly
    new_lease = lock_mgr.acquire("temp_key", owner="agent_recovered")
    assert new_lease.owner == "agent_recovered"
    lock_mgr.release("temp_key", owner="agent_recovered")


def test_scratchpad_crud_and_atomic_cas(scratchpad):
    # Set and get
    entry = scratchpad.set("target_dir", "/build/dist", agent_id="agent_planner")
    assert entry.version == 1
    assert entry.value == "/build/dist"
    assert entry.last_modified_by == "agent_planner"

    # CAS with correct version succeeds
    cas_ok = scratchpad.compare_and_set("target_dir", expected_version=1, new_value="/build/prod", agent_id="agent_lead")
    assert cas_ok is True
    assert scratchpad.get("target_dir") == "/build/prod"
    assert scratchpad.get_entry("target_dir").version == 2

    # CAS with stale version fails
    cas_fail = scratchpad.compare_and_set("target_dir", expected_version=1, new_value="/build/stale", agent_id="agent_bad")
    assert cas_fail is False
    assert scratchpad.get("target_dir") == "/build/prod"


def test_scratchpad_atomic_counter_and_list(scratchpad):
    scratchpad.set("task_count", 0, agent_id="init")
    c1 = scratchpad.atomic_increment("task_count", delta=5, agent_id="worker_1")
    assert c1 == 5
    c2 = scratchpad.atomic_increment("task_count", delta=2, agent_id="worker_2")
    assert c2 == 7

    # List append
    scratchpad.append_list("completed_tasks", "lint", agent_id="worker_1")
    scratchpad.append_list("completed_tasks", "build", agent_id="worker_2")
    assert scratchpad.get("completed_tasks") == ["lint", "build"]

    # Audit trail verification
    audit = scratchpad.get_audit_history()
    assert len(audit) >= 4
    assert any(a.action == "cas" or a.action == "set" for a in audit)
