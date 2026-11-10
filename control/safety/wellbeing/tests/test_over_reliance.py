"""
Tests for Over-Reliance Guard (10.55)
Verifies decision-deferral tracking, agency assertions, and wellbeing warning injection.
"""

import pytest
from control.safety.wellbeing.over_reliance_guard import (
    DEFAULT_WELLBEING_WARNING,
    OverRelianceGuard,
)


@pytest.fixture
def guard():
    return OverRelianceGuard(threshold=10)


def test_deferral_detection(guard):
    assert guard.is_decision_deferral("What should I do about this situation?") is True
    assert guard.is_decision_deferral("You decide for me, I cannot make up my mind.") is True
    assert guard.is_decision_deferral("Tell me what to do.") is True
    assert guard.is_decision_deferral("Should I quit my job?") is True
    assert guard.is_decision_deferral("Which one should I choose? You choose.") is True

    # Benign factual inquiries are NOT deferrals
    assert guard.is_decision_deferral("What is the distance to the moon?") is False
    assert guard.is_decision_deferral("Summarize this document for me.") is False


def test_agency_assertion(guard):
    assert guard.is_agency_assertion("I decided to take the offer.") is True
    assert guard.is_agency_assertion("My choice is option B.") is True
    assert guard.is_agency_assertion("I will go with the first design.") is True
    assert guard.is_agency_assertion("I disagree with that approach.") is True
    assert guard.is_agency_assertion("What should I do?") is False


def test_ten_consecutive_deferrals_triggers_warning(guard):
    """Acceptance Test: 10 consecutive 'what should I do?' -> over-reliance warning."""
    user = "user_deferral_test"

    # Turns 1 through 9: No warning
    for i in range(1, 10):
        warn, msg, count = guard.evaluate_turn(user, "What should I do?")
        assert warn is False
        assert msg is None
        assert count == i

    # Turn 10: Warning must trigger!
    warn_10, msg_10, count_10 = guard.evaluate_turn(user, "What should I do?")
    assert warn_10 is True
    assert msg_10 == DEFAULT_WELLBEING_WARNING
    assert count_10 == 10


def test_agency_assertion_resets_counter(guard):
    user = "user_reset_test"

    # 5 deferrals
    for _ in range(5):
        guard.evaluate_turn(user, "You decide for me.")
    assert guard.get_state(user).consecutive_deferrals == 5

    # User asserts agency
    warn, msg, count = guard.evaluate_turn(user, "Actually, I decided to decline the offer.")
    assert warn is False
    assert count == 0
    assert guard.get_state(user).consecutive_deferrals == 0

    # Next deferral starts at 1 again
    warn, msg, count = guard.evaluate_turn(user, "Now what should I do next?")
    assert count == 1
    assert warn is False


def test_user_and_tenant_isolation(guard):
    user1 = "user_1"
    user2 = "user_2"

    for _ in range(10):
        guard.evaluate_turn(user1, "Tell me what to do.", tenant_id="tenant_A")

    assert guard.get_state(user1, "tenant_A").consecutive_deferrals == 10
    # user2 has 0
    assert guard.get_state(user2, "tenant_A").consecutive_deferrals == 0
    # user1 in tenant_B has 0
    assert guard.get_state(user1, "tenant_B").consecutive_deferrals == 0

