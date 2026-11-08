"""
Pheonix Subscription Plans Catalog
Maintains active subscription configurations, tiers, quotas, and renewal schedules.
"""

from typing import Dict, List, Optional
from ..models import SubscriptionPlan


class PlanRegistry:
    """Manages active subscription plans across model providers."""

    def __init__(self):
        self._plans: Dict[str, SubscriptionPlan] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        defaults = [
            SubscriptionPlan(
                plan_id="openai-tier-2",
                provider="openai",
                name="OpenAI Scale Tier 2",
                monthly_cost_usd=0.0,
                monthly_quota_usd=500.0,
                billing_cycle="monthly",
                renewal_day_of_month=1
            ),
            SubscriptionPlan(
                plan_id="anthropic-pro",
                provider="anthropic",
                name="Anthropic Claude Pro / API Scale",
                monthly_cost_usd=20.0,
                monthly_quota_usd=250.0,
                billing_cycle="monthly",
                renewal_day_of_month=15
            ),
            SubscriptionPlan(
                plan_id="gemini-payg",
                provider="gemini",
                name="Google AI Studio Pay-As-You-Go",
                monthly_cost_usd=0.0,
                monthly_quota_usd=1000.0,
                billing_cycle="monthly",
                renewal_day_of_month=1
            ),
            SubscriptionPlan(
                plan_id="mistral-commercial",
                provider="mistral",
                name="Mistral AI Platform Commercial",
                monthly_cost_usd=0.0,
                monthly_quota_usd=300.0,
                billing_cycle="monthly",
                renewal_day_of_month=20
            ),
        ]
        for p in defaults:
            self.register_plan(p)

    def register_plan(self, plan: SubscriptionPlan) -> None:
        key = f"{plan.tenant_id}:{plan.provider.lower()}"
        self._plans[key] = plan

    def get_plan(self, provider: str, tenant_id: str = "default") -> Optional[SubscriptionPlan]:
        key = f"{tenant_id}:{provider.lower()}"
        if key in self._plans:
            return self._plans[key]
        default_key = f"default:{provider.lower()}"
        return self._plans.get(default_key)

    def list_plans(self, tenant_id: Optional[str] = None) -> List[SubscriptionPlan]:
        if tenant_id:
            return [p for p in self._plans.values() if p.tenant_id == tenant_id]
        return list(self._plans.values())
