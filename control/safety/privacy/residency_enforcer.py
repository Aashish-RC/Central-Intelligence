"""
Data Residency and Geo-Fencing Enforcer (Feature 10.32)
Enforces geographical data boundary constraints (e.g., GDPR EU residency, APAC, US).
Ensures EU users' prompts, completions, diagnostic payloads, and telemetry
are routed strictly to EU-region model endpoints and EU storage sinks,
preventing unauthorized cross-border transfers to US or external regions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class DataRegion(str, Enum):
    EU = "eu"
    US = "us"
    APAC = "apac"
    GLOBAL = "global"


class ResidencyViolationError(PermissionError):
    """Raised when data residency geo-fencing constraints are violated."""
    def __init__(self, message: str, user_id: str, user_region: str, target_region: str):
        super().__init__(message)
        self.user_id = user_id
        self.user_region = user_region
        self.target_region = target_region


REGIONAL_MODEL_ENDPOINTS: Dict[str, Dict[DataRegion, str]] = {
    "azure_openai": {
        DataRegion.EU: "https://ci-eu-francecentral.openai.azure.com",
        DataRegion.US: "https://ci-us-east.openai.azure.com",
        DataRegion.APAC: "https://ci-apac-singapore.openai.azure.com",
        DataRegion.GLOBAL: "https://ci-us-east.openai.azure.com",
    },
    "bedrock": {
        DataRegion.EU: "https://bedrock-runtime.eu-central-1.amazonaws.com",
        DataRegion.US: "https://bedrock-runtime.us-east-1.amazonaws.com",
        DataRegion.APAC: "https://bedrock-runtime.ap-southeast-1.amazonaws.com",
        DataRegion.GLOBAL: "https://bedrock-runtime.us-east-1.amazonaws.com",
    },
    "signoz": {
        DataRegion.EU: "https://signoz-collector.eu.central-intelligence.internal:4317",
        DataRegion.US: "https://signoz-collector.us.central-intelligence.internal:4317",
        DataRegion.APAC: "https://signoz-collector.apac.central-intelligence.internal:4317",
        DataRegion.GLOBAL: "https://signoz-collector.us.central-intelligence.internal:4317",
    },
}

# Regex to detect region from arbitrary endpoint URLs
REGION_PATTERNS = [
    (re.compile(r"(?i)\b(?:eu|europe|westeurope|germanywestcentral|francecentral|eu-central-1|eu-west-1)\b"), DataRegion.EU),
    (re.compile(r"(?i)\b(?:us|usa|eastus|westus|us-east-1|us-west-2)\b"), DataRegion.US),
    (re.compile(r"(?i)\b(?:apac|asia|tokyo|singapore|ap-southeast-1)\b"), DataRegion.APAC),
]


def detect_endpoint_region(url: str) -> DataRegion:
    for pat, region in REGION_PATTERNS:
        if pat.search(url):
            return region
    return DataRegion.GLOBAL


@dataclass
class UserResidencyProfile:
    user_id: str
    tenant_id: str = "default"
    primary_region: DataRegion = DataRegion.GLOBAL
    allowed_regions: Set[DataRegion] = field(default_factory=lambda: {DataRegion.GLOBAL})
    strict: bool = True


class DataResidencyEnforcer:
    """
    Enforces geographic residency constraints across model routing,
    telemetry ingestion, and storage sinks (Feature 10.32).
    """

    def __init__(self, default_region: DataRegion = DataRegion.GLOBAL):
        self.default_region = default_region
        self._profiles: Dict[str, UserResidencyProfile] = {}

    def _key(self, user_id: str, tenant_id: str = "default") -> str:
        return f"{tenant_id}:{user_id}"

    def set_user_residency(
        self,
        user_id: str,
        region: DataRegion | str,
        tenant_id: str = "default",
        allowed_regions: Optional[List[DataRegion | str]] = None,
        strict: bool = True,
    ) -> UserResidencyProfile:
        reg = DataRegion(region) if isinstance(region, str) else region
        allowed: Set[DataRegion] = {reg}
        if allowed_regions:
            for r in allowed_regions:
                allowed.add(DataRegion(r) if isinstance(r, str) else r)

        profile = UserResidencyProfile(
            user_id=user_id,
            tenant_id=tenant_id,
            primary_region=reg,
            allowed_regions=allowed,
            strict=strict,
        )
        self._profiles[self._key(user_id, tenant_id)] = profile
        return profile

    def get_user_residency(self, user_id: str, tenant_id: str = "default") -> UserResidencyProfile:
        k = self._key(user_id, tenant_id)
        if k not in self._profiles:
            # Check if user configured in any tenant
            for prof in self._profiles.values():
                if prof.user_id == user_id:
                    return prof
            return UserResidencyProfile(
                user_id=user_id,
                tenant_id=tenant_id,
                primary_region=self.default_region,
                allowed_regions={self.default_region},
            )
        return self._profiles[k]

    def is_dispatch_allowed(
        self,
        user_id: str,
        target_region: DataRegion | str,
        tenant_id: str = "default",
    ) -> bool:
        """
        Returns True if data for this user is permitted to be transferred
        or processed in target_region.
        """
        t_reg = DataRegion(target_region) if isinstance(target_region, str) else target_region
        profile = self.get_user_residency(user_id, tenant_id)

        # Global profiles can dispatch anywhere
        if profile.primary_region == DataRegion.GLOBAL and DataRegion.GLOBAL in profile.allowed_regions:
            return True

        # Strict EU user: must strictly stay in EU
        if profile.primary_region == DataRegion.EU:
            return t_reg == DataRegion.EU or t_reg in profile.allowed_regions

        return t_reg in profile.allowed_regions or t_reg == profile.primary_region

    def assert_compliant_dispatch(
        self,
        user_id: str,
        target_region: DataRegion | str,
        target_service: str = "model_endpoint",
        tenant_id: str = "default",
    ) -> None:
        """
        Raises ResidencyViolationError if sending user data to target_region is prohibited.
        """
        t_reg = DataRegion(target_region) if isinstance(target_region, str) else target_region
        if not self.is_dispatch_allowed(user_id, t_reg, tenant_id):
            prof = self.get_user_residency(user_id, tenant_id)
            raise ResidencyViolationError(
                f"Data residency policy violation: User '{user_id}' is geo-fenced to '{prof.primary_region.value}', "
                f"cannot transmit data to '{t_reg.value}' ({target_service}).",
                user_id=user_id,
                user_region=prof.primary_region.value,
                target_region=t_reg.value,
            )

    def resolve_regional_endpoint(
        self,
        user_id: str,
        service_name: str,
        tenant_id: str = "default",
    ) -> str:
        """
        Resolves the compliant regional URL for a service (e.g., Azure OpenAI, Bedrock, SigNoz).
        Guarantees that an EU user always receives an EU-region endpoint.
        """
        prof = self.get_user_residency(user_id, tenant_id)
        service_map = REGIONAL_MODEL_ENDPOINTS.get(service_name.lower())
        if not service_map:
            raise KeyError(f"No regional endpoints registered for service '{service_name}'")

        region = prof.primary_region
        if region in service_map:
            return service_map[region]

        # Fallback to GLOBAL or first allowed
        return service_map.get(DataRegion.GLOBAL, list(service_map.values())[0])


# Global default residency enforcer singleton
default_residency_enforcer = DataResidencyEnforcer()

