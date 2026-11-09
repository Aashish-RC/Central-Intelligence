"""Tests for OpenFGA Google Zanzibar ReBAC Adapter (Task 12.2)."""

import pytest
import time
from control.identity.openfga_adapter import OpenFGAAdapter


def test_openfga_rebac_check_acceptance():
    """Acceptance Test: openfga_client.check_permission(user='alice', action='can_edit', resource='document:123') returns True/False."""
    fga = OpenFGAAdapter()

    # Alice is editor of doc 123
    fga.write_tuple(user="user:alice", relation="editor", object="document:123")
    # Bob is owner of doc 456
    fga.write_tuple(user="user:bob", relation="owner", object="document:456")

    # Alice can edit doc:123
    assert fga.check_permission(user="alice", action="can_edit", resource="document:123") is True
    # Alice can view doc:123 (derived from editor)
    assert fga.check_permission(user="alice", action="can_view", resource="document:123") is True
    # Alice cannot share doc:123 (only owner can share)
    assert fga.check_permission(user="alice", action="can_share", resource="document:123") is False

    # Alice cannot edit doc:456
    assert fga.check_permission(user="alice", action="can_edit", resource="document:456") is False

    # Bob is owner, so Bob can share, edit, and view doc:456
    assert fga.check_permission(user="bob", action="can_share", resource="document:456") is True
    assert fga.check_permission(user="bob", action="can_edit", resource="document:456") is True
    assert fga.check_permission(user="bob", action="can_view", resource="document:456") is True


def test_openfga_context_aware_abac():
    """Validates attribute-based and context-aware conditions on tuples."""
    fga = OpenFGAAdapter()

    # Tuple with context constraint: internal network only
    fga.write_tuple(
        user="user:charlie",
        relation="viewer",
        object="document:classified",
        condition={"network": "vpn"},
    )

    # Allowed when context matches
    assert fga.check_permission(
        user="charlie",
        action="can_view",
        resource="document:classified",
        context={"network": "vpn"},
    ) is True

    # Denied when context differs
    assert fga.check_permission(
        user="charlie",
        action="can_view",
        resource="document:classified",
        context={"network": "public_wifi"},
    ) is False


def test_openfga_delegated_scoped_access():
    """Validates delegated access with scoped, expiring rights for sub-agents."""
    fga = OpenFGAAdapter()

    grant = fga.grant_delegation(
        delegator="user:dave",
        delegatee="agent:summary_bot",
        capabilities=["can_view"],
        resource_pattern="document:annual_report",
        ttl_seconds=3600,
    )

    # Sub-agent has delegated view permission
    assert fga.check_permission(user="agent:summary_bot", action="can_view", resource="document:annual_report") is True

    # But not edit permission
    assert fga.check_permission(user="agent:summary_bot", action="can_edit", resource="document:annual_report") is False

