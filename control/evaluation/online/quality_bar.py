"""Per-Domain and Per-Tenant Quality Bars (Layer 11: Evaluation & Quality, Feature 11.12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class QualityBarResult:
    """Check result against configured domain/tenant quality bar."""
    domain: str
    tenant_id: str
    actual_score: float
    required_bar: float
    meets_bar: bool


class QualityBarManager:
    """Maintains minimum required quality bars per domain and tenant tier."""

    DEFAULT_BARS: Dict[str, float] = {
        "finance": 0.95,
        "healthcare": 0.98,
        "legal": 0.95,
        "software": 0.85,
        "general": 0.80,
    }

    def __init__(self, tenant_overrides: Optional[Dict[str, Dict[str, float]]] = None):
        self.tenant_overrides = tenant_overrides or {}

    def get_bar(self, domain: str, tenant_id: str = "default") -> float:
        if tenant_id in self.tenant_overrides:
            if domain in self.tenant_overrides[tenant_id]:
                return self.tenant_overrides[tenant_id][domain]
        return self.DEFAULT_BARS.get(domain, 0.80)

    def check(self, actual_score: float, domain: str, tenant_id: str = "default") -> QualityBarResult:
        required = self.get_bar(domain, tenant_id)
        return QualityBarResult(
            domain=domain,
            tenant_id=tenant_id,
            actual_score=actual_score,
            required_bar=required,
            meets_bar=actual_score >= required,
        )
