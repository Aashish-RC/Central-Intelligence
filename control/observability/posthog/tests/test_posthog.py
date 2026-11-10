"""Test Suite for PostHog Product Analytics Adapter.
(Layer 14: Features 14.22, 14.23, 14.24)
"""

import time
import pytest
from control.observability.posthog import PostHogAdapter


@pytest.fixture
def posthog():
    return PostHogAdapter()


def test_1_event_capture(posthog):
    """Test 1: Analytics events are captured with user distinct_id and structured properties."""
    ev = posthog.capture(
        distinct_id="alice",
        event_name="model_called",
        properties={"model": "gpt-4o", "tokens": 150},
    )
    assert ev.distinct_id == "alice"
    assert ev.event_name == "model_called"
    assert ev.properties["model"] == "gpt-4o"
    assert len(posthog._events) == 1


def test_2_funnel_conversion_and_dropoff(posthog):
    """Test 2: Multi-step conversion funnel (signup -> first_conversation -> first_tool_use)."""
    now = time.time()
    steps = ["user_signup", "first_conversation", "first_tool_use"]

    # Alice completes all 3 steps
    posthog.capture("alice", "user_signup", timestamp=now)
    posthog.capture("alice", "first_conversation", timestamp=now + 60)
    posthog.capture("alice", "first_tool_use", timestamp=now + 120)

    # Bob completes steps 1 and 2, but drops off before tool use
    posthog.capture("bob", "user_signup", timestamp=now + 10)
    posthog.capture("bob", "first_conversation", timestamp=now + 70)

    # Charlie only signs up (step 1)
    posthog.capture("charlie", "user_signup", timestamp=now + 20)

    funnel = posthog.compute_funnel(steps)
    assert len(funnel) == 3

    # Step 1: 3 users
    assert funnel[0].step_name == "user_signup"
    assert funnel[0].users_reached == 3
    assert funnel[0].conversion_rate_from_start == 100.0

    # Step 2: 2 users (Alice, Bob)
    assert funnel[1].step_name == "first_conversation"
    assert funnel[1].users_reached == 2
    assert funnel[1].conversion_rate_from_start == pytest.approx(66.67, abs=0.1)
    assert funnel[1].drop_off_count == 1

    # Step 3: 1 user (Alice)
    assert funnel[2].step_name == "first_tool_use"
    assert funnel[2].users_reached == 1
    assert funnel[2].conversion_rate_from_start == pytest.approx(33.33, abs=0.1)
    assert funnel[2].drop_off_count == 1


def test_3_feature_adoption_metrics(posthog):
    """Test 3: Feature adoption tracks unique users and invocation volume (14.23)."""
    posthog.capture("alice", "feature_invoked", properties={"feature": "web_search"})
    posthog.capture("alice", "feature_invoked", properties={"feature": "web_search"})
    posthog.capture("bob", "feature_invoked", properties={"feature": "web_search"})
    posthog.capture("bob", "feature_invoked", properties={"feature": "code_interpreter"})

    adoption = posthog.get_feature_adoption()
    assert "web_search" in adoption
    assert adoption["web_search"]["unique_users_count"] == 2
    assert adoption["web_search"]["total_invocations"] == 3

    assert "code_interpreter" in adoption
    assert adoption["code_interpreter"]["unique_users_count"] == 1
    assert adoption["code_interpreter"]["total_invocations"] == 1


def test_4_session_replay_stream(posthog):
    """Test 4: Session interaction stream records UI actions for replay (14.22)."""
    sess_id = "session_xyz"
    posthog.record_session_replay_event(sess_id, "alice", "click", {"target": "run_agent_button"})
    posthog.record_session_replay_event(sess_id, "alice", "stream_token", {"token": "Hello"})
    posthog.record_session_replay_event(sess_id, "alice", "stream_token", {"token": " world!"})

    stream = posthog.get_session_replay(sess_id)
    assert len(stream) == 3
    assert stream[0]["event_type"] == "click"
    assert stream[2]["payload"]["token"] == " world!"

