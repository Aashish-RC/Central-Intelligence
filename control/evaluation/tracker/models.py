"""
Pheonix Subscription & Key Tracker Data Models
Defines schema for provider subscription plans, renewals, active key quotas, and alerts.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

BillingCycle = Literal["monthly", "annual", "pay_as_you_go"]
AlertLevel = Literal["normal", "warning", "critical", "exhausted"]
RenewalStatus = Literal["active", "due_soon", "overdue"]


class SubscriptionPlan(BaseModel):
    """Configuration representing a subscribed provider tier or plan."""
    plan_id: str
    tenant_id: str = "default"
    provider: str
    name: str
    monthly_cost_usd: float = Field(default=0.0, ge=0.0)
    monthly_quota_usd: float = Field(default=100.0, ge=0.0)
    billing_cycle: BillingCycle = "monthly"
    renewal_day_of_month: int = Field(default=1, ge=1, le=31)


class KeyQuotaStatus(BaseModel):
    """Real-time operational health and quota consumption of a provider key."""
    key_id: str
    tenant_id: str = "default"
    provider: str
    is_active: bool = True
    current_spend_usd: float = Field(default=0.0, ge=0.0)
    monthly_quota_usd: float = Field(default=100.0, ge=0.0)
    quota_used_percent: float = Field(default=0.0, ge=0.0)
    alert_level: AlertLevel = "normal"
    expires_at: Optional[str] = None  # YYYY-MM-DD
    is_expired: bool = False


class ProviderRenewal(BaseModel):
    """Upcoming renewal countdown and estimated cost for a provider subscription."""
    provider: str
    tenant_id: str = "default"
    plan_name: str
    next_renewal_date: str  # YYYY-MM-DD
    days_remaining: int
    estimated_renewal_cost_usd: float = Field(default=0.0, ge=0.0)
    status: RenewalStatus = "active"
