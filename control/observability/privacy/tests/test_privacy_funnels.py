"""
Unit tests for Differential Privacy-Preserving Funnels (14.22).
"""

import time
import numpy as np
import pytest
from control.observability.posthog.posthog_adapter import PostHogAdapter
from control.observability.privacy.privacy_funnels import (
    DifferentialFunnelReport,
    FunnelEvent,
    FunnelStats,
    PrivacyFunnels,
)


def test_aggregate_funnel_laplace_noise():
    """Verify aggregate_funnel algorithm applies Laplace noise calibrated to epsilon."""
    epsilon = 0.5
    funnel = PrivacyFunnels(epsilon=epsilon)

    # 100 true events
    events = [FunnelEvent(user_id=f"u_{i}", event_name="login") for i in range(100)]

    stats = funnel.aggregate_funnel(events)
    assert isinstance(stats, FunnelStats)
    assert stats.epsilon == 0.5
    assert stats.privacy_guaranteed is True
    # Due to Laplace noise, count should be non-negative and close to 100 but not necessarily identical
    assert stats.count >= 0
    # Over 50 repeated runs, verify noise variance exists (not deterministic raw count)
    counts = [funnel.aggregate_funnel(events).count for _ in range(50)]
    assert len(set(counts)) > 1  # Non-deterministic differential noise


def test_individual_privacy_protection():
    """
    Acceptance: Doesn't reveal individual user behavior.
    An adversary observing aggregate count cannot determine if a single user participated.
    """
    funnel = PrivacyFunnels(epsilon=1.0)
    # Single user event
    single_user_events = [FunnelEvent(user_id="target_user", event_name="secret_action")]

    counts = [funnel.aggregate_funnel(single_user_events).count for _ in range(100)]
    # Due to Laplace noise, outputs vary around 1 (e.g. 0, 1, 2, 3), masking target_user presence
    assert any(c == 0 for c in counts)
    assert any(c > 1 for c in counts)


def test_aggregate_trends_preserved():
    """
    Acceptance: Funnel data shows aggregate trends.
    A large cohort with true 50% drop-off retains clear downward trend under DP.
    """
    funnel = PrivacyFunnels(epsilon=1.0)

    # Large cohort: 2000 signups -> 1000 first_queries -> 500 tool_uses
    events = []
    now = time.time()
    for i in range(2000):
        uid = f"user_{i}"
        events.append(FunnelEvent(user_id=uid, event_name="signup", timestamp=now))
        if i < 1000:
            events.append(FunnelEvent(user_id=uid, event_name="first_query", timestamp=now + 10))
        if i < 500:
            events.append(FunnelEvent(user_id=uid, event_name="tool_use", timestamp=now + 20))

    report = funnel.compute_private_funnel(
        step_names=["signup", "first_query", "tool_use"],
        events=events,
    )

    assert isinstance(report, DifferentialFunnelReport)
    assert len(report.steps) == 3

    step0 = report.steps[0]
    step1 = report.steps[1]
    step2 = report.steps[2]

    # Trend clearly visible: ~2000 > ~1000 > ~500
    assert step0.noisy_users_reached > step1.noisy_users_reached > step2.noisy_users_reached
    assert step0.noisy_users_reached == pytest.approx(2000, abs=50)
    assert step1.noisy_users_reached == pytest.approx(1000, abs=50)
    assert step2.noisy_users_reached == pytest.approx(500, abs=50)

    # Conversion rate approximately 50% for step 1
    assert step1.noisy_conversion_rate == pytest.approx(50.0, abs=5.0)


def test_posthog_wiring():
    """Verify PrivacyFunnels pulls raw events from PostHog adapter automatically."""
    posthog = PostHogAdapter()
    for i in range(10):
        posthog.capture(f"user_{i}", "onboarding_start")
        if i < 7:
            posthog.capture(f"user_{i}", "onboarding_complete")

    funnel = PrivacyFunnels(epsilon=2.0, posthog_adapter=posthog)
    report = funnel.compute_private_funnel(["onboarding_start", "onboarding_complete"])

    assert len(report.steps) == 2
    assert report.steps[0].step_name == "onboarding_start"
    assert report.steps[1].step_name == "onboarding_complete"
    assert report.privacy_guaranteed is True
