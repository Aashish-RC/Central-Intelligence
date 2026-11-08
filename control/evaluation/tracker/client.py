"""
Pheonix Tracker Client SDK
Provides APIs to inspect provider subscription renewals, active key quotas, and alerts.
"""

from datetime import date
from typing import List, Optional
from .models import KeyQuotaStatus, ProviderRenewal, SubscriptionPlan
from .core.plans import PlanRegistry
from .core.renewal_engine import RenewalEngine
from .core.key_monitor import KeyMonitor


class TrackerClient:
    """Client for monitoring subscriptions, renewals, and API key statuses."""

    def __init__(
        self,
        plan_registry: Optional[PlanRegistry] = None,
        key_monitor: Optional[KeyMonitor] = None
    ):
        self.plans = plan_registry or PlanRegistry()
        self.key_monitor = key_monitor or KeyMonitor(plan_registry=self.plans)

    def list_active_keys(self, tenant_id: Optional[str] = None) -> List[KeyQuotaStatus]:
        """Lists all active provider keys with quota consumption."""
        return self.key_monitor.list_keys(only_active=True, tenant_id=tenant_id)

    def list_all_keys(self, tenant_id: Optional[str] = None) -> List[KeyQuotaStatus]:
        """Lists all registered keys (both active and inactive/revoked)."""
        return self.key_monitor.list_keys(only_active=False, tenant_id=tenant_id)

    def list_upcoming_renewals(
        self,
        reference_date: Optional[date] = None,
        tenant_id: Optional[str] = None,
    ) -> List[ProviderRenewal]:
        """Lists all upcoming provider subscription renewals ordered by urgency."""
        plans = self.plans.list_plans(tenant_id=tenant_id)
        return RenewalEngine.list_renewals(plans, reference_date=reference_date)

    def deduct_usage(
        self,
        provider: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
        key_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[KeyQuotaStatus]:
        """Deducts quota by adding real token usage/cost reported by observability."""
        return self.key_monitor.deduct_usage(
            provider=provider, tokens=tokens, cost_usd=cost_usd, key_id=key_id, tenant_id=tenant_id
        )

    def aggregate_licenses(self, tenant_id: Optional[str] = None):
        """Aggregates multi-account key licenses, quotas, and spends per provider."""
        return self.key_monitor.aggregate_licenses(tenant_id=tenant_id)

    def purge_expired_keys(self, reference_date: Optional[date] = None) -> List[str]:
        """Purges expired or invalid keys from tracking."""
        return self.key_monitor.purge_expired_keys(reference_date=reference_date)

    def render_dashboard(
        self,
        reference_date: Optional[date] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Renders formatted ASCII dashboard showing active keys and upcoming renewals."""
        keys = self.list_all_keys(tenant_id=tenant_id)
        renewals = self.list_upcoming_renewals(reference_date=reference_date, tenant_id=tenant_id)

        lines = [
            "============================================================",
            "  Pheonix Subscription & Key Tracker Dashboard",
            "============================================================",
            "Active Keys & Quota Consumption:",
        ]
        for k in keys:
            status_flag = "ACTIVE" if k.is_active else "INACTIVE"
            lines.append(
                f"  - [{status_flag:<8}] {k.key_id:<20} | {k.provider:<10} | Spend: ${k.current_spend_usd:>6.2f} / ${k.monthly_quota_usd:>6.2f} ({k.quota_used_percent:>5.1f}%) [{k.alert_level.upper()}]"
            )

        lines.append("------------------------------------------------------------")
        lines.append("Upcoming Subscription Renewals:")
        for r in renewals:
            lines.append(
                f"  - {r.provider:<10} | Renewal: {r.next_renewal_date} (in {r.days_remaining:>2} days) | Cost: ${r.estimated_renewal_cost_usd:.2f} [{r.status.upper()}]"
            )
        lines.append("============================================================")
        return "\n".join(lines)
