"""
Pheonix Key Status & Quota Monitor
Tracks active provider keys, monitors spend against monthly quotas, and triggers alerts.
"""

from datetime import date
from typing import Dict, List, Optional, Any
from ..models import KeyQuotaStatus, AlertLevel, SubscriptionPlan
from .plans import PlanRegistry


class KeyMonitor:
    """Tracks active provider credentials, quota limits, and usage percentages."""

    def __init__(self, plan_registry: Optional[PlanRegistry] = None):
        self.plans = plan_registry or PlanRegistry()
        self._key_records: Dict[str, KeyQuotaStatus] = {}
        self._init_mock_keys()

    def _init_mock_keys(self) -> None:
        """Initializes default tracked provider keys."""
        default_keys = [
            ("key-openai-prod", "openai", True, 84.50),
            ("key-anthropic-prod", "anthropic", True, 195.00),
            ("key-gemini-prod", "gemini", True, 45.00),
            ("key-mistral-backup", "mistral", False, 0.00),
        ]
        for key_id, provider, active, spend in default_keys:
            self.register_key(key_id=key_id, provider=provider, is_active=active, current_spend=spend)

    def register_key(
        self,
        key_id: str,
        provider: str,
        is_active: bool = True,
        current_spend: float = 0.0,
        monthly_quota_usd: Optional[float] = None,
        expires_at: Optional[str] = None,
        tenant_id: str = "default",
    ) -> KeyQuotaStatus:
        plan = self.plans.get_plan(provider, tenant_id=tenant_id)
        quota = monthly_quota_usd if monthly_quota_usd is not None else (plan.monthly_quota_usd if plan else 100.0)
        used_percent = round((current_spend / quota) * 100.0, 1) if quota > 0 else 0.0

        alert: AlertLevel = "normal"
        if used_percent >= 100.0:
            alert = "exhausted"
        elif used_percent >= 85.0:
            alert = "critical"
        elif used_percent >= 70.0:
            alert = "warning"

        is_expired = False
        if expires_at:
            try:
                exp_date = date.fromisoformat(expires_at)
                if exp_date < date.today():
                    is_expired = True
                    is_active = False
            except Exception:
                pass

        status = KeyQuotaStatus(
            key_id=key_id,
            tenant_id=tenant_id,
            provider=provider,
            is_active=is_active,
            current_spend_usd=current_spend,
            monthly_quota_usd=quota,
            quota_used_percent=used_percent,
            alert_level=alert,
            expires_at=expires_at,
            is_expired=is_expired
        )
        self._key_records[key_id] = status
        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="tracker",
                action="key_registered",
                tenant_id=tenant_id,
                resource=key_id,
                status="success",
                details={"provider": provider, "monthly_quota_usd": quota, "current_spend_usd": current_spend},
            )
        except Exception:
            pass
        return status

    def deduct_usage(
        self,
        provider: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
        key_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[KeyQuotaStatus]:
        """Deducts quota by adding real token usage/cost from observability and updating alerts."""
        prov = provider.lower()
        target_record = None

        if key_id and key_id in self._key_records:
            target_record = self._key_records[key_id]
        else:
            for r in self._key_records.values():
                if r.provider.lower() == prov and r.is_active:
                    if tenant_id is None or r.tenant_id == tenant_id:
                        target_record = r
                        break

        if not target_record:
            return None

        deduction = cost_usd
        if deduction <= 0.0 and tokens > 0:
            deduction = round((tokens / 1000.0) * 0.002, 4)

        target_record.current_spend_usd = round(target_record.current_spend_usd + deduction, 4)
        if target_record.monthly_quota_usd > 0:
            target_record.quota_used_percent = round(
                (target_record.current_spend_usd / target_record.monthly_quota_usd) * 100.0, 1
            )
        else:
            target_record.quota_used_percent = 0.0

        if target_record.quota_used_percent >= 100.0:
            target_record.alert_level = "exhausted"
        elif target_record.quota_used_percent >= 85.0:
            target_record.alert_level = "critical"
        elif target_record.quota_used_percent >= 70.0:
            target_record.alert_level = "warning"
        else:
            target_record.alert_level = "normal"

        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="tracker",
                action="deduct_usage",
                tenant_id=target_record.tenant_id,
                resource=target_record.key_id,
                status="success",
                details={
                    "provider": target_record.provider,
                    "deduction_usd": deduction,
                    "tokens": tokens,
                    "current_spend_usd": target_record.current_spend_usd,
                    "alert_level": target_record.alert_level,
                },
            )
        except Exception:
            pass

        return target_record

    def purge_expired_keys(self, reference_date: Optional[date] = None) -> List[str]:
        """
        Purges expired keys or explicitly inactive keys with past expiry dates.
        Returns list of purged key IDs.
        """
        ref = reference_date or date.today()
        purged: List[str] = []

        for key_id, record in list(self._key_records.items()):
            should_purge = False
            if record.is_expired:
                should_purge = True
            elif record.expires_at:
                try:
                    exp_date = date.fromisoformat(record.expires_at)
                    if exp_date < ref:
                        should_purge = True
                except Exception:
                    pass

            if should_purge:
                del self._key_records[key_id]
                purged.append(key_id)

        return purged

    def aggregate_licenses(self, tenant_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Aggregates multi-account licenses, spend, and quotas grouped by provider.
        """
        aggregated: Dict[str, Dict[str, Any]] = {}
        records = [
            r for r in self._key_records.values()
            if tenant_id is None or r.tenant_id == tenant_id
        ]
        for record in records:
            prov = record.provider.lower()
            if prov not in aggregated:
                aggregated[prov] = {
                    "provider": prov,
                    "total_keys": 0,
                    "active_keys": 0,
                    "total_spend_usd": 0.0,
                    "total_quota_usd": 0.0,
                    "quota_used_percent": 0.0,
                    "alert_level": "normal"
                }

            agg = aggregated[prov]
            agg["total_keys"] += 1
            if record.is_active:
                agg["active_keys"] += 1
            agg["total_spend_usd"] = round(agg["total_spend_usd"] + record.current_spend_usd, 2)
            agg["total_quota_usd"] = round(agg["total_quota_usd"] + record.monthly_quota_usd, 2)

        for prov, agg in aggregated.items():
            t_quota = agg["total_quota_usd"]
            t_spend = agg["total_spend_usd"]
            pct = round((t_spend / t_quota) * 100.0, 1) if t_quota > 0 else 0.0
            agg["quota_used_percent"] = pct
            if pct >= 100.0:
                agg["alert_level"] = "exhausted"
            elif pct >= 85.0:
                agg["alert_level"] = "critical"
            elif pct >= 70.0:
                agg["alert_level"] = "warning"
            else:
                agg["alert_level"] = "normal"

        return aggregated

    def get_key_status(self, key_id: str) -> Optional[KeyQuotaStatus]:
        return self._key_records.get(key_id)

    def list_keys(
        self,
        provider: Optional[str] = None,
        only_active: bool = False,
        tenant_id: Optional[str] = None,
    ) -> List[KeyQuotaStatus]:
        keys = list(self._key_records.values())
        if tenant_id:
            keys = [k for k in keys if k.tenant_id == tenant_id]
        if provider:
            keys = [k for k in keys if k.provider.lower() == provider.lower()]
        if only_active:
            keys = [k for k in keys if k.is_active]
        return keys
