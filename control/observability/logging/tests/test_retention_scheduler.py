"""
Unit tests for Log Retention Scheduler & Cleanup Engine (14.20).
"""

import time
import pytest
from control.safety.pii import DataClass, FourTierPIIScrubber, RetentionPolicy
from control.observability.logging.retention_scheduler import (
    RetentionScheduler,
    RetentionPolicyOverride,
    DEFAULT_RETENTION_TTLS,
)


class MockConsentManager:
    """Mock Consent Manager for testing c15t privacy mode."""
    def __init__(self, privacy_users=None):
        self.privacy_users = set(privacy_users or [])

    def is_privacy_mode(self, user_id: str, tenant_id: str = "default") -> bool:
        return user_id in self.privacy_users


def test_default_retention_ttls():
    scheduler = RetentionScheduler()
    assert scheduler.get_retention("user_normal", DataClass.DIAGNOSTIC) == 14
    assert scheduler.get_retention("user_normal", DataClass.TELEMETRY) == 365
    assert scheduler.get_retention("user_normal", DataClass.AUDIT) == 365
    assert scheduler.get_retention("user_normal", DataClass.ZDR) == 0


def test_privacy_mode_zero_retention():
    """Acceptance criteria: privacy-mode user has zero retention (ZDR)."""
    consent_mock = MockConsentManager(privacy_users=["user_private_123"])
    scheduler = RetentionScheduler(consent_manager=consent_mock)

    policy = scheduler.get_retention("user_private_123", DataClass.DIAGNOSTIC)
    assert isinstance(policy, RetentionPolicy)
    assert policy.ttl_days == 0
    assert scheduler.get_retention_days("user_private_123", DataClass.DIAGNOSTIC) == 0

    # Normal user should still get default 14 days
    assert scheduler.get_retention("user_other", DataClass.DIAGNOSTIC) == 14


def test_custom_user_tenant_retention_override():
    """User/tenant-configurable TTLs per data class."""
    scheduler = RetentionScheduler()
    scheduler.set_user_override(
        user_id="user_enterprise",
        policy_or_ttl=RetentionPolicyOverride(
            user_id="user_enterprise",
            telemetry_ttl_days=30,
            diagnostic_ttl_days=7,
            audit_ttl_days=180,
        ),
    )

    assert scheduler.get_retention("user_enterprise", DataClass.DIAGNOSTIC) == 7
    assert scheduler.get_retention("user_enterprise", DataClass.TELEMETRY) == 30
    assert scheduler.get_retention("user_enterprise", DataClass.AUDIT) == 180


def test_cleanup_expired_logs_older_than_14_days():
    """Acceptance criteria: logs older than 14 days deleted."""
    scrubber = FourTierPIIScrubber()
    scheduler = RetentionScheduler(scrubber=scrubber)

    # Store a record in Tier 2 Diagnostic Store
    now = time.time()
    old_time = now - (15 * 86400)  # 15 days ago (older than 14-day TTL)
    recent_time = now - (2 * 86400)  # 2 days ago (within 14-day TTL)

    # Directly populate diagnostic records
    scrubber.tier2.store("Recent log: user logged in", user_id="user_1", ttl_days=14)
    scrubber.tier2.store("Old log: debug session", user_id="user_2", ttl_days=14)

    # Adjust created_at / expires_at of old log to simulate 15 days elapsed
    records = list(scrubber.tier2._records.values())
    assert len(records) == 2

    # Make record 1 old
    records[1].created_at = old_time
    records[1].expires_at = old_time + (14 * 86400)

    # Also add telemetry records in Tier 1
    rec1 = scrubber.tier1.store({"metric_id": "m1", "latency_ms": 120.0}, user_id="user_1", retained_days=90)
    rec2 = scrubber.tier1.store({"metric_id": "m2", "latency_ms": 150.0}, user_id="user_2", retained_days=14)
    rec2.timestamp = old_time

    assert len(scrubber.tier2._records) == 2
    assert len(scrubber.tier1._records) == 2

    # Run cleanup sweep
    result = scheduler.cleanup_expired(current_time=now)

    assert result["tier2_purged"] >= 1
    assert result["tier1_purged"] >= 1
    assert result["total_purged"] >= 2

    # Verify that the old diagnostic record is gone from storage and recent one remains
    assert len(scrubber.tier2._records) == 1
    remaining_record = list(scrubber.tier2._records.values())[0]
    assert remaining_record.user_id == "user_1"


