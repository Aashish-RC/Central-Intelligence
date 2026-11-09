"""Tests for Agent Identity, Credentials, Attribution & Mutual Auth (Task 12.4)."""

import pytest
import time
from control.identity.agent.agent_identity import AgentIdentityManager


def test_agent_credential_and_action_attribution_acceptance():
    """Acceptance Test: Sub-agent gets a 15-minute scoped token; after task completes, token expires; all actions attributed to agent + parent user."""
    mgr = AgentIdentityManager()

    # 1. Register agent bound to parent user
    agent = mgr.register_agent(
        agent_id="bot_deep_researcher",
        name="Deep Researcher",
        parent_user_id="user_alice",
        tenant_id="acme_corp",
        capabilities={"web_search", "document_summary"},
    )
    assert agent.parent_user_id == "user_alice"

    # 2. Issue 15-minute (900s) scoped credential
    cred = mgr.issue_credential(
        agent_id="bot_deep_researcher",
        task_id="task_999",
        ttl_seconds=900,
    )
    assert cred.token.startswith("agt_")
    assert cred.is_valid() is True
    assert (cred.expires_at - cred.issued_at) == 900

    # 3. Verify action attribution to both agent and parent user
    attr = mgr.record_attributed_action(
        token=cred.token,
        action_name="web_search",
        details={"query": "quantum gravity research 2026"},
    )
    assert attr.agent_id == "bot_deep_researcher"
    assert attr.parent_user_id == "user_alice"
    assert attr.task_id == "task_999"

    # 4. Task completes -> token expires or revoked
    mgr.revoke_credential(cred.token)
    assert cred.is_valid() is False

    with pytest.raises(PermissionError, match="revoked"):
        mgr.verify_credential(cred.token)


def test_agent_capability_scoping():
    """Validates capability restriction enforcement on agent credentials."""
    mgr = AgentIdentityManager()
    mgr.register_agent(
        agent_id="bot_read_only",
        name="Read Only Bot",
        parent_user_id="user_bob",
        capabilities={"read_docs"},
    )

    cred = mgr.issue_credential("bot_read_only", capabilities={"read_docs"})

    # Has read capability
    assert mgr.verify_credential(cred.token, required_capability="read_docs") is not None

    # Lacks write capability
    with pytest.raises(PermissionError, match="lacks required capability"):
        mgr.verify_credential(cred.token, required_capability="write_docs")


def test_agent_mutual_authentication():
    """Validates mutual agent-to-agent cryptographic handshake."""
    mgr = AgentIdentityManager()

    # Agent A delegates to Agent B
    token = mgr.generate_m2m_handshake(source_agent_id="agent_planner", target_agent_id="agent_coder")

    # Agent B verifies handshake
    valid, source = mgr.verify_m2m_handshake(token, expected_target_agent_id="agent_coder")
    assert valid is True
    assert source == "agent_planner"

    # Impersonation / wrong target fails
    valid_bad, err = mgr.verify_m2m_handshake(token, expected_target_agent_id="agent_imposter")
    assert valid_bad is False
    assert "mismatch" in err.lower()
