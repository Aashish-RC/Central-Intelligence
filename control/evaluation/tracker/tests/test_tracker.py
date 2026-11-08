"""
Pheonix Subscription and Key Tracker Test Suite
Verifies subscription plan management, renewal countdowns, quota monitoring, and active keys listing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import date
import pytest
from tracker.models import SubscriptionPlan, KeyQuotaStatus, ProviderRenewal
from tracker.core.plans import PlanRegistry
from tracker.core.renewal_engine import RenewalEngine
from tracker.core.key_monitor import KeyMonitor
from tracker.client import TrackerClient


class TestPlanRegistry:
    """Tests subscription plan catalog management."""

    def test_default_plans_loaded(self):
        registry = PlanRegistry()
        plans = registry.list_plans()
        providers = [p.provider for p in plans]

        assert "openai" in providers
        assert "anthropic" in providers
        assert "gemini" in providers
        assert "mistral" in providers

    def test_registers_custom_plan(self):
        registry = PlanRegistry()
        custom = SubscriptionPlan(
            plan_id="groq-enterprise",
            provider="groq",
            name="Groq Ultra LPU Tier",
            monthly_cost_usd=50.0,
            monthly_quota_usd=1000.0,
            renewal_day_of_month=5
        )
        registry.register_plan(custom)
        retrieved = registry.get_plan("groq")

        assert retrieved is not None
        assert retrieved.monthly_cost_usd == 50.0
        assert retrieved.renewal_day_of_month == 5


class TestRenewalEngine:
    """Tests renewal date and countdown calculations."""

    def test_calculates_renewal_within_same_month(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=25
        )
        ref_date = date(2026, 10, 20)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2026-10-25"
        assert renewal.days_remaining == 5
        assert renewal.status == "active"

    def test_calculates_renewal_rollover_to_next_month(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=5
        )
        ref_date = date(2026, 10, 20)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2026-11-05"
        assert renewal.days_remaining == 16

    def test_marks_due_soon_when_under_three_days(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=23
        )
        ref_date = date(2026, 10, 21)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.days_remaining == 2
        assert renewal.status == "due_soon"

    def test_handles_december_to_january_rollover(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=1
        )
        ref_date = date(2026, 12, 15)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2027-01-01"
        assert renewal.days_remaining == 17


class TestKeyMonitor:
    """Tests key status and quota threshold alerting."""

    def test_normal_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-1", "openai", is_active=True, current_spend=50.0)
        assert status.quota_used_percent == 10.0
        assert status.alert_level == "normal"

    def test_warning_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-2", "openai", is_active=True, current_spend=360.0)
        assert status.quota_used_percent == 72.0
        assert status.alert_level == "warning"

    def test_critical_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-3", "openai", is_active=True, current_spend=440.0)
        assert status.quota_used_percent == 88.0
        assert status.alert_level == "critical"

    def test_exhausted_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-4", "openai", is_active=True, current_spend=520.0)
        assert status.quota_used_percent == 104.0
        assert status.alert_level == "exhausted"


class TestTrackerVerificationGate:
    """Verification Gate: 'Done when: Renewals and active keys are listed'."""

    def test_renewals_and_active_keys_are_listed(self):
        client = TrackerClient()

        # 1. Active keys listing
        active_keys = client.list_active_keys()
        assert len(active_keys) >= 3
        for key in active_keys:
            assert key.is_active is True
            assert key.monthly_quota_usd > 0
            assert key.quota_used_percent >= 0

        # 2. Upcoming renewals listing
        renewals = client.list_upcoming_renewals(reference_date=date(2026, 10, 21))
        assert len(renewals) >= 4
        for r in renewals:
            assert r.days_remaining >= 0
            assert r.next_renewal_date is not None
            assert r.provider in ["openai", "anthropic", "gemini", "mistral"]

        # 3. Dashboard output includes both
        dashboard = client.render_dashboard(reference_date=date(2026, 10, 21))
        assert "Pheonix Subscription & Key Tracker Dashboard" in dashboard
        assert "Active Keys & Quota Consumption" in dashboard
        assert "Upcoming Subscription Renewals" in dashboard
        assert "openai" in dashboard
        assert "anthropic" in dashboard


class TestTrackerRenewalAndExpiryHardening:
    """Task 4.6: Tracker Renewal & Expiry Tests."""

    def test_expiry_countdown_triggers_and_thresholds(self):
        """Verify countdown thresholds trigger due_soon and calculate exact remaining days."""
        plan = SubscriptionPlan(
            plan_id="plan-aws",
            provider="aws-bedrock",
            name="Bedrock Reserved",
            renewal_day_of_month=28
        )

        # 7 days remaining -> active
        r7 = RenewalEngine.calculate_renewal(plan, reference_date=date(2026, 10, 21))
        assert r7.days_remaining == 7
        assert r7.status == "active"

        # 3 days remaining -> due_soon boundary
        r3 = RenewalEngine.calculate_renewal(plan, reference_date=date(2026, 10, 25))
        assert r3.days_remaining == 3
        assert r3.status == "due_soon"

        # 1 day remaining -> due_soon
        r1 = RenewalEngine.calculate_renewal(plan, reference_date=date(2026, 10, 27))
        assert r1.days_remaining == 1
        assert r1.status == "due_soon"

    def test_leap_year_february_renewal_countdown(self):
        """Verify leap year handling (Feb 29 vs Feb 28 clamping)."""
        plan = SubscriptionPlan(
            plan_id="plan-leap",
            provider="cohere",
            name="Cohere Command Tier",
            renewal_day_of_month=31  # Provider renews on last day of month
        )

        # Leap year 2028: February has 29 days
        r_leap = RenewalEngine.calculate_renewal(plan, reference_date=date(2028, 2, 10))
        assert r_leap.next_renewal_date == "2028-02-29"
        assert r_leap.days_remaining == 19

        # Non-leap year 2027: February has 28 days
        r_non_leap = RenewalEngine.calculate_renewal(plan, reference_date=date(2027, 2, 10))
        assert r_non_leap.next_renewal_date == "2027-02-28"
        assert r_non_leap.days_remaining == 18

    def test_multi_account_license_aggregation(self):
        """Verify multi-account licenses aggregated across providers with correct spend and quotas."""
        registry = PlanRegistry()
        monitor = KeyMonitor(plan_registry=registry)

        # Clear mock keys for clean isolation
        monitor._key_records.clear()

        # Add 3 OpenAI keys with different spends and custom quotas
        monitor.register_key("key-oai-dept-a", "openai", is_active=True, current_spend=200.0, monthly_quota_usd=500.0)
        monitor.register_key("key-oai-dept-b", "openai", is_active=True, current_spend=250.0, monthly_quota_usd=500.0)
        monitor.register_key("key-oai-dept-c", "openai", is_active=False, current_spend=0.0, monthly_quota_usd=100.0)

        # Add 2 Anthropic keys
        monitor.register_key("key-claude-prod", "anthropic", is_active=True, current_spend=350.0, monthly_quota_usd=400.0)
        monitor.register_key("key-claude-dev", "anthropic", is_active=True, current_spend=40.0, monthly_quota_usd=100.0)

        aggregated = monitor.aggregate_licenses()

        assert "openai" in aggregated
        assert "anthropic" in aggregated

        oai_agg = aggregated["openai"]
        assert oai_agg["total_keys"] == 3
        assert oai_agg["active_keys"] == 2
        assert oai_agg["total_spend_usd"] == 450.0
        assert oai_agg["total_quota_usd"] == 1100.0
        assert oai_agg["quota_used_percent"] == round((450.0 / 1100.0) * 100.0, 1)  # ~40.9%
        assert oai_agg["alert_level"] == "normal"

        claude_agg = aggregated["anthropic"]
        assert claude_agg["total_keys"] == 2
        assert claude_agg["active_keys"] == 2
        assert claude_agg["total_spend_usd"] == 390.0
        assert claude_agg["total_quota_usd"] == 500.0
        assert claude_agg["quota_used_percent"] == 78.0  # 390/500 = 78% -> warning
        assert claude_agg["alert_level"] == "warning"

    def test_expired_key_purge(self):
        """Verify purging expired keys removes outdated records while active keys remain."""
        monitor = KeyMonitor()
        monitor._key_records.clear()

        ref_date = date(2026, 10, 22)

        # 1. Valid active key (expires in 2027)
        monitor.register_key("key-live", "openai", is_active=True, expires_at="2027-01-01")

        # 2. Key expired yesterday
        monitor.register_key("key-expired-1", "openai", is_active=True, expires_at="2026-10-21")

        # 3. Key expired last month
        monitor.register_key("key-expired-2", "anthropic", is_active=False, expires_at="2026-09-15")

        # 4. Key without expiry
        monitor.register_key("key-perpetual", "gemini", is_active=True, expires_at=None)

        assert len(monitor.list_keys()) == 4

        # Purge keys relative to ref_date
        purged = monitor.purge_expired_keys(reference_date=ref_date)

        assert set(purged) == {"key-expired-1", "key-expired-2"}
        assert len(monitor.list_keys()) == 2
        remaining_ids = {k.key_id for k in monitor.list_keys()}
        assert remaining_ids == {"key-live", "key-perpetual"}

        # Running purge again is idempotent
        purged_again = monitor.purge_expired_keys(reference_date=ref_date)
        assert purged_again == []
