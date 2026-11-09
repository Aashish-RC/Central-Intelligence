"""Unit tests for Per-Agent Memory Partition & Isolation (5.38)."""

import pytest
from cognitive.action.sandboxes.memory_partition import (
    MemoryPartitionManager,
    MemoryIsolationViolationError,
)


def test_agent_partition_isolation():
    manager = MemoryPartitionManager()

    # Agent A writes private facts
    manager.write_fact("agent_alpha", "db_password", "alpha_secret_pw")
    manager.write_fact("agent_alpha", "cluster_endpoint", "alpha.internal:5432")

    # Agent A can read its own facts
    val = manager.read_fact("agent_alpha", "db_password", caller_agent_id="agent_alpha")
    assert val == "alpha_secret_pw"

    # Agent B attempts to read Agent A's facts without permission -> blocked!
    with pytest.raises(MemoryIsolationViolationError, match="unauthorized to read"):
        manager.read_fact("agent_alpha", "db_password", caller_agent_id="agent_beta")

    # Agent B attempts to write into Agent A's partition -> blocked!
    with pytest.raises(MemoryIsolationViolationError, match="unauthorized to write"):
        manager.write_fact("agent_alpha", "db_password", "poisoned_value", caller_agent_id="agent_beta")


def test_explicit_acl_sharing_and_revocation():
    manager = MemoryPartitionManager()
    manager.write_fact("agent_alpha", "shared_token", "jwt_token_alpha")

    # Grant read access to Agent Beta
    manager.grant_access("agent_alpha", "agent_beta", access_type="read")

    # Agent Beta can now read
    val = manager.read_fact("agent_alpha", "shared_token", caller_agent_id="agent_beta")
    assert val == "jwt_token_alpha"

    # Agent Beta still cannot write
    with pytest.raises(MemoryIsolationViolationError, match="unauthorized to write"):
        manager.write_fact("agent_alpha", "shared_token", "tampered", caller_agent_id="agent_beta")

    # Revoke access
    manager.revoke_access("agent_alpha", "agent_beta", access_type="read")
    with pytest.raises(MemoryIsolationViolationError, match="unauthorized to read"):
        manager.read_fact("agent_alpha", "shared_token", caller_agent_id="agent_beta")


def test_admin_super_access_and_teardown():
    manager = MemoryPartitionManager()
    manager.write_fact("agent_alpha", "ephemeral_state", "active_running")

    # Admin caller bypasses isolation
    val = manager.read_fact("agent_alpha", "ephemeral_state", caller_agent_id="admin")
    assert val == "active_running"

    facts = manager.list_facts("agent_alpha", caller_agent_id="admin")
    assert facts["ephemeral_state"] == "active_running"

    # Clear partition upon task finish
    manager.clear_partition("agent_alpha")
    assert manager.read_fact("agent_alpha", "ephemeral_state") is None
