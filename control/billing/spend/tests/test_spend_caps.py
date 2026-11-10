"""
Tests for Spend Caps & Real-Time Alerts (Feature 13.11).
"""

from unittest.mock import MagicMock
import pytest

from control.billing.spend.spend_caps import (
    AlertLevel,
    SpendCapManager,
)


def test_eighty_percent_email_alert_and_one_hundred_percent_agent_paused():
    """
    Acceptance criterion: 80% -> email alert; 100% -> agent paused.
    """
    mock_email_dispatcher = MagicMock(return_value=True)
    manager = SpendCapManager(email_notifier=mock_email_dispatcher)

    user_id = "user_spend_test_100"
    user_email = "tester@enterprise.io"

    # Set a $100.00 monthly cap
    manager.set_spend_cap(user_id=user_id, monthly_cap_usd=100.0, email=user_email)

    # 1. Spend $50.00 (50%) -> Nominal, no alert, agent allowed
    res1 = manager.track_spend(user_id=user_id, amount_usd=50.0)
    assert res1.percentage == 50.0
    assert res1.action == "continue"
    assert res1.is_agent_paused is False
    assert manager.is_agent_allowed(user_id)[0] is True
    assert mock_email_dispatcher.call_count == 0

    # 2. Spend another $32.00 (Total $82.00, 82%) -> Triggers 80% email alert!
    res2 = manager.track_spend(user_id=user_id, amount_usd=32.0)
    assert res2.percentage == 82.0
    assert res2.action == "alert_80_sent"
    assert res2.is_agent_paused is False
    assert manager.is_agent_allowed(user_id)[0] is True

    # Verify email notification was dispatched
    assert mock_email_dispatcher.call_count == 1
    call_args = mock_email_dispatcher.call_args[0]
    assert call_args[0] == user_email
    assert "80%" in call_args[1]

    # Additional spend within 80-99% does not duplicate 80% email
    manager.track_spend(user_id=user_id, amount_usd=5.0)  # $87.00
    assert mock_email_dispatcher.call_count == 1

    # 3. Spend another $15.00 (Total $102.00, 102%) -> Triggers 100% hard cap, PAUSES agent!
    res3 = manager.track_spend(user_id=user_id, amount_usd=15.0)
    assert res3.percentage == 102.0
    assert res3.action == "agent_paused"
    assert res3.is_agent_paused is True

    # Agent is now blocked from executing
    allowed, reason = manager.is_agent_allowed(user_id)
    assert allowed is False
    assert "Agent paused: 100% monthly spend cap" in reason

    # Hard cap alert email was sent
    assert mock_email_dispatcher.call_count == 2
    assert "100% Spend Cap" in mock_email_dispatcher.call_args[0][1]


def test_resume_agent_on_cap_increase():
    manager = SpendCapManager()
    user_id = "user_resume_test"
    manager.set_spend_cap(user_id, monthly_cap_usd=50.0)

    # Exceed cap
    manager.track_spend(user_id, amount_usd=55.0)
    assert manager.is_agent_allowed(user_id)[0] is False

    # Increase cap to $100 and resume
    manager.resume_agent(user_id, new_cap_usd=100.0)
    assert manager.is_agent_allowed(user_id)[0] is True
    assert manager.get_policy(user_id).monthly_cap_usd == 100.0
