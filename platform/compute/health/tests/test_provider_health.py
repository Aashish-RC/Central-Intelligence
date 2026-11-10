"""Unit tests for ProviderHealthTracker (Task 16.4)."""

import time
import pytest
from platform.compute.health.provider_health import (
    ProviderHealthTracker,
    ProviderStatus,
)


@pytest.fixture
def tracker():
    return ProviderHealthTracker(failure_threshold=3, recovery_threshold=2)


def test_provider_down_and_recovery_lifecycle(tracker: ProviderHealthTracker):
    """Acceptance test: Provider down -> unhealthy; recovery -> healthy."""
    provider = "anthropic"

    assert tracker.is_available(provider) is True
    assert tracker.get_status(provider) == ProviderStatus.HEALTHY

    # Record 1st failure -> degraded
    status1 = tracker.record_failure(provider, "502 Bad Gateway", status_code=502)
    assert status1 == ProviderStatus.DEGRADED
    assert tracker.is_available(provider) is True

    # Record 2nd failure -> degraded
    status2 = tracker.record_failure(provider, "502 Bad Gateway", status_code=502)
    assert status2 == ProviderStatus.DEGRADED

    # Record 3rd failure -> reaches threshold -> DOWN
    status3 = tracker.record_failure(provider, "504 Gateway Timeout", status_code=504)
    assert status3 == ProviderStatus.DOWN
    assert tracker.is_available(provider) is False
    assert tracker.get_status(provider) == ProviderStatus.DOWN

    # Provider begins recovering: 1st success -> still DEGRADED, needs 2 successes
    status_rec1 = tracker.record_success(provider)
    assert status_rec1 == ProviderStatus.DEGRADED

    # 2nd success -> recovers to HEALTHY
    status_rec2 = tracker.record_success(provider)
    assert status_rec2 == ProviderStatus.HEALTHY
    assert tracker.is_available(provider) is True


def test_rate_limiting_cooldown(tracker: ProviderHealthTracker):
    """HTTP 429 triggers RATE_LIMITED state until cooldown expires."""
    provider = "openai"

    tracker.record_failure(
        provider,
        "Rate limit exceeded. Please try again later.",
        status_code=429,
        retry_after_seconds=1.0,
    )
    assert tracker.get_status(provider) == ProviderStatus.RATE_LIMITED
    assert tracker.is_available(provider) is False

    # Simulate fast-forwarding time past cooldown
    report = tracker.get_report(provider)
    assert report.rate_limited_until is not None
    report.rate_limited_until = time.time() - 1

    # Now available again for probing
    assert tracker.is_available(provider) is True
    assert tracker.get_status(provider) in (ProviderStatus.DEGRADED, ProviderStatus.HEALTHY)

