"""Lago Quarantined Billing Engine Adapter (Layer 13: Features 13.01–13.05, 13.14–13.16).

IMPORTANT LICENSE NOTICE:
Lago is licensed under AGPL-3.0. In accordance with platform quarantine policy:
- No Lago Python libraries or internal code are imported into this process.
- All integration is performed strictly over boundary network REST APIs (HTTP / JSON).
- The adapter supports hermetic / offline execution with in-memory state fallbacks.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx

from control.billing.models import BillingInvoice, SubscriptionTier
from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.billing.engine")


@dataclass
class PlanDefinition:
    plan_code: str
    name: str
    tier: SubscriptionTier
    monthly_token_quota: int
    price_cents_monthly: int
    allowed_models: List[str] = field(default_factory=list)
    features_enabled: List[str] = field(default_factory=list)
    overage_allowed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomerSubscription:
    subscription_id: str
    customer_id: str
    plan_code: str
    status: str = "active"  # 'active', 'past_due', 'canceled', 'suspended'
    tokens_used_this_period: int = 0
    period_start: float = field(default_factory=time.time)
    period_end: float = 0.0
    wallet_balance_cents: int = 0

    def __post_init__(self):
        if self.period_end == 0.0:
            self.period_end = self.period_start + (30 * 86400)


class LagoAdapter:
    """Quarantined REST interface to Lago usage-based billing platform."""

    def __init__(
        self,
        api_url: str = "http://localhost:3000",
        api_key: Optional[str] = None,
        _defer_prod_check: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key or "lago_local_test_key"
        self._client: Optional[httpx.Client] = None
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("lago")
        )

        # Embedded state cache ensuring functionality in hermetic test and offline environments
        self._plans: Dict[str, PlanDefinition] = {}
        self._subscriptions: Dict[str, CustomerSubscription] = {}
        self._invoices: List[BillingInvoice] = []

        # Initialize default platform tiers
        self._init_default_plans()

    def _http_client(self) -> httpx.Client:
        """Cached httpx.Client bound to api_url with 5-second timeout."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.api_url,
                timeout=5.0,
            )
        return self._client

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _init_default_plans(self) -> None:
        self.create_plan(
            PlanDefinition(
                plan_code="free",
                name="Developer Free Tier",
                tier=SubscriptionTier.FREE,
                monthly_token_quota=10_000,
                price_cents_monthly=0,
                allowed_models=["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash"],
                features_enabled=["chat", "search"],
                overage_allowed=False,
            )
        )
        self.create_plan(
            PlanDefinition(
                plan_code="pro",
                name="Pro Professional Tier",
                tier=SubscriptionTier.PRO,
                monthly_token_quota=100_000,
                price_cents_monthly=2000,  # $20.00 / month
                allowed_models=["gpt-4o", "claude-3-5-sonnet", "o3-mini"],
                features_enabled=["chat", "search", "code_execution", "memory_snapshots"],
                overage_allowed=True,
            )
        )

    def create_plan(self, plan: PlanDefinition) -> PlanDefinition:
        """Defines a billing plan with quota and model restrictions."""
        self._plans[plan.plan_code] = plan
        return plan

    def get_plan(self, plan_code: str) -> Optional[PlanDefinition]:
        return self._plans.get(plan_code)

    def subscribe_customer(
        self,
        customer_id: str,
        plan_code: str,
        initial_credits_cents: int = 0,
    ) -> CustomerSubscription:
        """Assigns customer/tenant to a billing plan (13.14)."""
        if plan_code not in self._plans:
            raise ValueError(f"Plan '{plan_code}' does not exist.")

        sub_id = f"sub_{int(time.time()*1000)}_{customer_id}"
        sub = CustomerSubscription(
            subscription_id=sub_id,
            customer_id=customer_id,
            plan_code=plan_code,
            status="active",
            wallet_balance_cents=initial_credits_cents,
        )
        self._subscriptions[customer_id] = sub

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            payload = {
                "customer": {
                    "external_id": customer_id,
                    "name": customer_id,
                    "email": f"{customer_id}@ci.local",
                }
            }
            try:
                resp = self._http_client().post(
                    "/api/v1/customers",
                    json=payload,
                    headers=self._auth_headers(),
                    timeout=5.0,
                )
                if resp.status_code not in (200, 201, 422):
                    fail_closed_in_production(
                        "lago", f"Lago create customer HTTP {resp.status_code}: {resp.text}"
                    )
                # Now create the subscription tied to the Lago plan code
                sub_payload = {
                    "subscription": {
                        "external_customer_id": customer_id,
                        "plan_code": plan_code,
                        "status": "active",
                    }
                }
                sub_resp = self._http_client().post(
                    "/api/v1/subscriptions",
                    json=sub_payload,
                    headers=self._auth_headers(),
                    timeout=5.0,
                )
                if sub_resp.status_code not in (200, 201, 422):
                    fail_closed_in_production(
                        "lago", f"Lago create subscription HTTP {sub_resp.status_code}: {sub_resp.text}"
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("lago", f"Lago subscribe failed: {exc}", cause=exc)

        return sub

    def check_entitlement(
        self,
        customer_id: str,
        requested_tokens: int,
        model: Optional[str] = None,
        feature: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Request-time gate: checks plan quota, model entitlement, and credits (13.05)."""
        sub = self._subscriptions.get(customer_id)
        if not sub:
            if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
                try:
                    c_resp = self._http_client().get(
                        f"/api/v1/customers/{customer_id}",
                        headers=self._auth_headers(),
                        timeout=5.0,
                    )
                    if c_resp.status_code == 200:
                        sub = CustomerSubscription(
                            subscription_id=f"sub_{customer_id}",
                            customer_id=customer_id,
                            plan_code="free",
                            status="active",
                        )
                        self._subscriptions[customer_id] = sub
                except ProductionSafetyError:
                    raise
                except Exception:
                    pass
            if not sub:
                sub = self.subscribe_customer(customer_id, "free")

        if sub.status != "active":
            return False, f"Subscription status is {sub.status}"

        plan = self._plans.get(sub.plan_code)
        if not plan:
            return False, f"Unknown plan '{sub.plan_code}'"

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                # Lago exposes entitlements via the customer's current subscription
                resp = self._http_client().get(
                    f"/api/v1/customers/{customer_id}/current_usage",
                    params={"external_subscription_id": sub.subscription_id},
                    headers=self._auth_headers(),
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    usage = resp.json().get("customer_usage", {})
                    tokens_used = int(usage.get("units", 0))
                    if tokens_used + requested_tokens > plan.monthly_token_quota:
                        if not plan.overage_allowed and sub.wallet_balance_cents <= 0:
                            return False, f"Monthly quota exhausted (used: {tokens_used})"
                    return True, "Authorized"
                fail_closed_in_production(
                    "lago", f"Lago usage query HTTP {resp.status_code}: {resp.text}"
                )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("lago", f"Lago entitlement check failed: {exc}", cause=exc)

        # 1. Model permission check (13.02)
        if model and plan.allowed_models:
            if model not in plan.allowed_models and not any(m in model for m in plan.allowed_models):
                return False, f"Model '{model}' is not included in {plan.name} entitlements."

        # 2. Feature entitlement check (13.02)
        if feature and plan.features_enabled:
            if feature not in plan.features_enabled:
                return False, f"Feature '{feature}' is not included in {plan.name}."

        # 3. Monthly token quota check (13.04)
        projected_tokens = sub.tokens_used_this_period + requested_tokens
        if projected_tokens > plan.monthly_token_quota:
            if not plan.overage_allowed:
                # Quota exceeded; check wallet credits
                if sub.wallet_balance_cents <= 0:
                    return False, f"Monthly quota of {plan.monthly_token_quota:,} tokens exhausted."

        return True, "Authorized"

    def record_usage(
        self,
        customer_id: str,
        tokens: int,
    ) -> CustomerSubscription:
        """Increments monthly usage counter and deducts overage credits if needed."""
        sub = self._subscriptions.get(customer_id)
        if not sub:
            sub = self.subscribe_customer(customer_id, "free")

        plan = self._plans.get(sub.plan_code)
        sub.tokens_used_this_period += tokens

        if plan and sub.tokens_used_this_period > plan.monthly_token_quota:
            if plan.overage_allowed:
                overage = sub.tokens_used_this_period - plan.monthly_token_quota
                # Deduct 1 cent per 1000 overage tokens
                charge_cents = int((overage / 1000) * 1)
                sub.wallet_balance_cents = max(0, sub.wallet_balance_cents - charge_cents)

        return sub

    def add_credits(self, customer_id: str, amount_cents: int) -> int:
        """Top-up customer wallet balance (13.15)."""
        sub = self._subscriptions.get(customer_id)
        if not sub:
            sub = self.subscribe_customer(customer_id, "free")
        sub.wallet_balance_cents += amount_cents
        return sub.wallet_balance_cents

    def generate_invoice(self, customer_id: str, tenant_id: str = "default") -> BillingInvoice:
        """Generates a billing invoice for the subscription period (13.13)."""
        sub = self._subscriptions.get(customer_id)
        if not sub:
            sub = self.subscribe_customer(customer_id, "free")

        plan = self._plans.get(sub.plan_code)
        base_cents = plan.price_cents_monthly if plan else 0

        inv = BillingInvoice(
            invoice_id=f"inv_{int(time.time()*1000)}_{str(uuid4())[:8]}",
            customer_id=customer_id,
            tenant_id=tenant_id,
            amount_cents=base_cents,
            currency="USD",
            status="open",
            line_items=[
                {
                    "description": f"{plan.name if plan else 'Subscription'} Monthly Fee",
                    "amount_cents": base_cents,
                },
                {
                    "description": f"Token Consumption ({sub.tokens_used_this_period:,} tokens)",
                    "amount_cents": 0,
                },
            ],
        )
        self._invoices.append(inv)

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                resp = self._http_client().post(
                    "/api/v1/invoices",
                    json={"invoice": {"external_customer_id": customer_id, "period": "monthly"}},
                    headers=self._auth_headers(),
                    timeout=5.0,
                )
                if resp.status_code not in (200, 201):
                    fail_closed_in_production(
                        "lago", f"Lago invoice create HTTP {resp.status_code}: {resp.text}"
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("lago", f"Lago invoice failed: {exc}", cause=exc)

        return inv

