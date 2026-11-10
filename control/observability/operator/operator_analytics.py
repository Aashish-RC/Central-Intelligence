"""
Operator Analytics & Cross-Tenant Inspection Tools (Layer 14: Feature 14.24).

Administrative inspection tools to analyze usage patterns across users and tenants.
Identifies heavy consumers, anomalous consumption spikes, cross-tenant trends,
and potential platform abuse. Wires into Layer 12 IAM Operator Console.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from control.identity.operator.console import OperatorConsole
from control.observability.signoz.signoz_adapter import SigNozAdapter

logger = logging.getLogger("control.observability.operator.analytics")


@dataclass
class UserUsageProfile:
    """Detailed operational consumption profile for an individual user across tenants."""
    user_id: str
    tenant_id: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    request_count: int
    error_count: int
    error_rate: float
    is_heavy_user: bool = False
    flagged_for_abuse: bool = False
    abuse_reasons: List[str] = field(default_factory=list)


@dataclass
class TenantAggregateUsage:
    """Aggregate utilization metrics for a tenant."""
    tenant_id: str
    active_users_count: int
    total_tokens: int
    total_cost_usd: float
    total_requests: int
    error_rate: float


@dataclass
class CrossTenantUsageReport:
    """Platform-wide operational audit report across all tenants."""
    timestamp: float
    time_window_seconds: float
    total_platform_requests: int
    total_platform_tokens: int
    total_platform_cost_usd: float
    tenants: List[TenantAggregateUsage]
    heavy_users: List[UserUsageProfile]
    flagged_abuse_candidates: List[UserUsageProfile]


class OperatorAnalytics:
    """
    Operator cross-tenant analytics engine (Feature 14.24).
    Empowers platform administrators to inspect cross-tenant patterns, track heavy users,
    and trigger interventions via Layer 12 OperatorConsole.
    """

    def __init__(
        self,
        signoz_adapter: Optional[SigNozAdapter] = None,
        operator_console: Optional[OperatorConsole] = None,
    ) -> None:
        self.signoz = signoz_adapter or SigNozAdapter()
        self.operator_console = operator_console or OperatorConsole()

    def get_cross_tenant_usage(
        self,
        window_seconds: float = 86400.0,
        current_time: Optional[float] = None,
    ) -> CrossTenantUsageReport:
        """
        Builds a comprehensive cross-tenant usage summary report.
        Acceptance: Admin can view cross-tenant usage patterns and identify heavy users.
        """
        now = current_time if current_time is not None else time.time()
        cutoff = now - window_seconds

        # Aggregate spans
        spans = [s for s in self.signoz._spans if s.start_time >= cutoff]
        metrics = [m for m in self.signoz._metrics if m.timestamp >= cutoff]

        user_profiles: Dict[str, UserUsageProfile] = {}
        tenant_users: Dict[str, Set[str]] = {}
        tenant_requests: Dict[str, int] = {}
        tenant_errors: Dict[str, int] = {}
        tenant_tokens: Dict[str, int] = {}
        tenant_costs: Dict[str, float] = {}

        for s in spans:
            tid = s.attributes.get("tenant_id", "default")
            uid = s.attributes.get("user_id", "anonymous")
            key = f"{tid}:{uid}"

            tenant_users.setdefault(tid, set()).add(uid)
            tenant_requests[tid] = tenant_requests.get(tid, 0) + 1
            is_err = getattr(s.status, "value", str(s.status)) == "error"
            if is_err:
                tenant_errors[tid] = tenant_errors.get(tid, 0) + 1

            if key not in user_profiles:
                user_profiles[key] = UserUsageProfile(
                    user_id=uid,
                    tenant_id=tid,
                    total_tokens=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_cost_usd=0.0,
                    request_count=0,
                    error_count=0,
                    error_rate=0.0,
                )

            user_profiles[key].request_count += 1
            if is_err:
                user_profiles[key].error_count += 1

        for m in metrics:
            tid = m.labels.get("tenant_id", "default")
            uid = m.labels.get("user_id", "anonymous")
            key = f"{tid}:{uid}"

            if key not in user_profiles:
                user_profiles[key] = UserUsageProfile(
                    user_id=uid,
                    tenant_id=tid,
                    total_tokens=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_cost_usd=0.0,
                    request_count=0,
                    error_count=0,
                    error_rate=0.0,
                )

            if m.name == "llm.tokens.total":
                user_profiles[key].total_tokens += int(m.value)
                tenant_tokens[tid] = tenant_tokens.get(tid, 0) + int(m.value)
            elif m.name == "llm.tokens.prompt":
                user_profiles[key].prompt_tokens += int(m.value)
            elif m.name == "llm.tokens.completion":
                user_profiles[key].completion_tokens += int(m.value)
            elif m.name == "llm.cost.usd":
                user_profiles[key].total_cost_usd += float(m.value)
                tenant_costs[tid] = tenant_costs.get(tid, 0.0) + float(m.value)

        # Compute error rates and abuse flags
        for profile in user_profiles.values():
            if profile.request_count > 0:
                profile.error_rate = profile.error_count / profile.request_count

            # Abuse heuristics: high error rate with many requests, or anomalous burst
            if profile.request_count >= 10 and profile.error_rate > 0.4:
                profile.flagged_for_abuse = True
                profile.abuse_reasons.append("High error rate failure burst (>40%)")

        all_tenants: Set[str] = set(tenant_users.keys()) | set(tenant_tokens.keys())
        tenant_aggregates: List[TenantAggregateUsage] = []
        for tid in sorted(all_tenants):
            reqs = tenant_requests.get(tid, 0)
            errs = tenant_errors.get(tid, 0)
            err_rate = (errs / reqs) if reqs > 0 else 0.0
            tenant_aggregates.append(
                TenantAggregateUsage(
                    tenant_id=tid,
                    active_users_count=len(tenant_users.get(tid, set())),
                    total_tokens=tenant_tokens.get(tid, 0),
                    total_cost_usd=round(tenant_costs.get(tid, 0.0), 4),
                    total_requests=reqs,
                    error_rate=round(err_rate, 4),
                )
            )

        # Classify heavy users
        profiles_list = list(user_profiles.values())
        heavy_users = self.identify_heavy_users(
            profiles_list,
            limit=10,
            threshold_tokens=500,
        )
        for h in heavy_users:
            h.is_heavy_user = True

        flagged = [p for p in profiles_list if p.flagged_for_abuse]

        total_platform_tokens = sum(t.total_tokens for t in tenant_aggregates)
        total_platform_cost = sum(t.total_cost_usd for t in tenant_aggregates)
        total_platform_requests = sum(t.total_requests for t in tenant_aggregates)

        return CrossTenantUsageReport(
            timestamp=now,
            time_window_seconds=window_seconds,
            total_platform_requests=total_platform_requests,
            total_platform_tokens=total_platform_tokens,
            total_platform_cost_usd=round(total_platform_cost, 4),
            tenants=tenant_aggregates,
            heavy_users=heavy_users,
            flagged_abuse_candidates=flagged,
        )

    def identify_heavy_users(
        self,
        profiles: Optional[List[UserUsageProfile]] = None,
        limit: int = 10,
        threshold_tokens: int = 1000,
        threshold_cost_usd: float = 0.05,
    ) -> List[UserUsageProfile]:
        """
        Ranks and identifies heavy users across the platform.
        """
        if profiles is None:
            report = self.get_cross_tenant_usage()
            profiles = list(report.heavy_users)

        candidates = [
            p for p in profiles
            if p.total_tokens >= threshold_tokens or p.total_cost_usd >= threshold_cost_usd
        ]
        # Sort by total tokens descending, then cost descending
        candidates.sort(key=lambda p: (p.total_tokens, p.total_cost_usd), reverse=True)
        return candidates[:limit]

    def pause_abusive_user(self, user_id: str, admin_id: str, reason: str) -> Any:
        """Directly intervenes via Layer 12 OperatorConsole to pause an abusive user."""
        return self.operator_console.pause_user_agents(user_id=user_id, admin_id=admin_id, reason=reason)


# Global default operator analytics instance
default_operator_analytics = OperatorAnalytics()

