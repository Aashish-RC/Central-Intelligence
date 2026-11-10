"""Data models for Entitlements & Billing (Layer 13).
Supports features 13.01–13.18.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


@dataclass
class TokenUsageEvent:
    """Standardized metering event representing tokens consumed during model invocation."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = "anon"
    tenant_id: str = "default"
    app_id: str = "default_app"
    model: str = "unknown"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    byok: bool = False
    billable: bool = True
    compute_provider: str = "cloud"  # 'local', 'byoi', 'cloud'
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class MeteredUsageSummary:
    """Aggregated token consumption and attribution metrics."""
    user_id: str
    tenant_id: str
    app_id: Optional[str] = None
    total_tokens: int = 0
    billable_tokens: int = 0
    byok_tokens: int = 0
    total_cost_usd: float = 0.0
    billable_cost_usd: float = 0.0
    events_count: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)


@dataclass
class PlanEntitlements:
    """Entitlements attached to a pricing tier."""
    tier: SubscriptionTier
    monthly_token_quota: int
    rpm_limit: int
    allowed_models: List[str]
    features_enabled: List[str]
    overage_allowed: bool = False
    price_cents_monthly: int = 0


@dataclass
class BillingInvoice:
    """Standardized representation of billing invoice generated for subscription / usage."""
    invoice_id: str
    customer_id: str
    tenant_id: str
    amount_cents: int
    currency: str = "USD"
    status: str = "draft"  # 'draft', 'open', 'paid', 'void', 'disputed'
    due_date: str = ""
    paid_at: Optional[str] = None
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
