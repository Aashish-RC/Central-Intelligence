"""Tests for Identity Financial Authority Bridge (Task 12.10, Feature 12.45)."""

import pytest
from cognitive.action.safety.financial_authority import FinancialAuthorityError, TransactionStatus
from control.identity.financial.authority_bridge import IdentityFinancialBridge


def test_user_spend_limit_checked_acceptance():
    """Acceptance Test: User's spend limit is checked before L5 allows a payment."""
    bridge = IdentityFinancialBridge()
    user_id = "user_cfo_01"
    agent_id = "agent_procurement"

    # Configure user with $500 single limit and $1000 daily budget
    bridge.set_user_limit(
        user_id=user_id,
        max_single_transaction_usd=500.0,
        daily_budget_usd=1000.0,
    )

    # 1. Payment within limit succeeds
    result = bridge.check_and_authorize_payment(
        user_id=user_id,
        agent_id=agent_id,
        amount_usd=250.0,
        recipient="Stripe:SaaS-Vendor",
        purpose="Monthly vector database hosting fee",
    )
    assert result.authorized is True
    assert result.status == TransactionStatus.APPROVED
    assert result.receipt_token is not None
    assert bridge.get_user_authority(user_id).spent_today_usd == 250.0

    # 2. Payment exceeding user single transaction limit ($600 > $500) raises error
    with pytest.raises(FinancialAuthorityError, match="exceeds user's single transaction limit"):
        bridge.check_and_authorize_payment(
            user_id=user_id,
            agent_id=agent_id,
            amount_usd=600.0,
            recipient="Cloud:GPU-Cluster",
            purpose="Hardware reservation",
        )

    # 3. Cumulative payment exceeding daily budget ($250 already spent)
    # Perform another $400 spend (total = $650 <= $1000)
    bridge.check_and_authorize_payment(
        user_id=user_id,
        agent_id=agent_id,
        amount_usd=400.0,
        recipient="Cloud:Hosting",
        purpose="Hosting fee",
    )
    assert bridge.get_user_authority(user_id).spent_today_usd == 650.0

    # Another $400 spend would total $1050 > $1000 -> raises error
    with pytest.raises(FinancialAuthorityError, match="exceed user's daily budget"):
        bridge.check_and_authorize_payment(
            user_id=user_id,
            agent_id=agent_id,
            amount_usd=400.0,
            recipient="AWS:Bedrock",
            purpose="Inference credits batch",
        )
