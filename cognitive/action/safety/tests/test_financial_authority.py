"""Unit tests for Financial Authority Guard (Features 5.46, 12.45)."""

import pytest
from cognitive.action.safety import (
    AgentFinancialPolicy,
    FinancialAuthorityGuard,
    FinancialAuthorityError,
    TransactionStatus,
)


@pytest.fixture
def guard():
    g = FinancialAuthorityGuard()
    policy = AgentFinancialPolicy(
        agent_id="agent_buyer",
        max_single_transaction_usd=100.0,
        daily_budget_usd=500.0,
        monthly_budget_usd=5000.0,
        dual_control_threshold_usd=1000.0,
        max_transactions_per_hour=5,
    )
    g.set_policy(policy)
    return g


def test_unregistered_agent_blocked(guard):
    tx = guard.evaluate_transaction(
        agent_id="rogue_agent",
        amount_usd=10.0,
        recipient="cloud_provider",
        purpose="Compute provisioning",
    )
    assert tx.status == TransactionStatus.BLOCKED
    assert any("no registered financial authority" in r for r in tx.reasons)


def test_within_budget_auto_approved(guard):
    tx = guard.evaluate_transaction(
        agent_id="agent_buyer",
        amount_usd=45.0,
        recipient="cloud_provider",
        purpose="Spot instance",
    )
    assert tx.status == TransactionStatus.APPROVED
    assert len(tx.reasons) == 0

    settled = guard.settle_transaction(tx.transaction_id)
    assert settled.status == TransactionStatus.SETTLED
    assert guard.get_remaining_daily_budget("agent_buyer") == 500.0 - 45.0


def test_single_transaction_cap_exceeded(guard):
    tx = guard.evaluate_transaction(
        agent_id="agent_buyer",
        amount_usd=150.0,  # Max is 100.0
        recipient="cloud_provider",
        purpose="Large dedicated node",
    )
    assert tx.status == TransactionStatus.PENDING_APPROVAL
    assert any("exceeds single transaction authority cap" in r for r in tx.reasons)

    # Supervisor signs off
    guard.add_authorization_signature(tx.transaction_id, signer_id="lead_architect")
    updated = guard.settle_transaction(tx.transaction_id)
    assert updated.status == TransactionStatus.SETTLED


def test_daily_budget_cap_exceeded(guard):
    # Spend 400 first
    tx1 = guard.evaluate_transaction(
        agent_id="agent_buyer",
        amount_usd=80.0,
        recipient="vendor",
        purpose="Licenses",
    )
    guard.settle_transaction(tx1.transaction_id)

    # Next spend would breach daily budget ($450 more would exceed $500)
    tx2 = guard.evaluate_transaction(
        agent_id="agent_buyer",
        amount_usd=450.0,
        recipient="vendor",
        purpose="Cluster expansion",
    )
    assert tx2.status == TransactionStatus.PENDING_APPROVAL
    assert any("exceeding daily budget" in r for r in tx2.reasons)


def test_dual_control_multisig_threshold(guard):
    # Configure an executive buyer with high single limit but $1000 dual-control threshold
    exec_policy = AgentFinancialPolicy(
        agent_id="agent_exec",
        max_single_transaction_usd=5000.0,
        daily_budget_usd=10000.0,
        monthly_budget_usd=50000.0,
        dual_control_threshold_usd=1000.0,
    )
    guard.set_policy(exec_policy)

    tx = guard.evaluate_transaction(
        agent_id="agent_exec",
        amount_usd=2500.0,
        recipient="infrastructure_partner",
        purpose="Annual compute reservation",
    )
    assert tx.status == TransactionStatus.PENDING_APPROVAL
    assert any("requires dual authorization signatures" in r for r in tx.reasons)

    # First signature -> still pending
    guard.add_authorization_signature(tx.transaction_id, signer_id="finance_director")
    assert tx.status == TransactionStatus.PENDING_APPROVAL

    # Second independent signature -> approved
    guard.add_authorization_signature(tx.transaction_id, signer_id="chief_security_officer")
    assert tx.status == TransactionStatus.APPROVED

    settled = guard.settle_transaction(tx.transaction_id)
    assert settled.status == TransactionStatus.SETTLED


def test_velocity_limit_exceeded(guard):
    for i in range(5):
        tx = guard.evaluate_transaction(
            agent_id="agent_buyer",
            amount_usd=5.0,
            recipient=f"micro_service_{i}",
            purpose=f"Call {i}",
        )
        guard.settle_transaction(tx.transaction_id)

    # 6th transaction in hour violates max 5/hour
    tx_blocked = guard.evaluate_transaction(
        agent_id="agent_buyer",
        amount_usd=5.0,
        recipient="micro_service_6",
        purpose="Call 6",
    )
    assert tx_blocked.status == TransactionStatus.BLOCKED
    assert any("Velocity limit exceeded" in r for r in tx_blocked.reasons)
