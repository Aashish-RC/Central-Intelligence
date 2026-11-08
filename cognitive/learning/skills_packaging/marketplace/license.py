"""Ecosystem Licensing: Tamper-evident HMAC license validation and tier entitlement checks."""

from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntitlementTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LicenseKey(BaseModel):
    key_id: str = Field(default_factory=lambda: f"lic_{uuid.uuid4().hex[:8]}")
    user_id: str
    tenant_id: str = "default_tenant"
    tier: EntitlementTier = EntitlementTier.FREE
    features: List[str] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    signature: str = ""


class LicenseService:
    """Issues and cryptographically verifies ecosystem license keys."""

    def __init__(self, secret_key: str = "pheonix_ecosystem_hmac_secret_2026"):
        self.secret_key = secret_key.encode("utf-8")

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hmac.new(self.secret_key, serialized, hashlib.sha256).hexdigest()

    def generate_license(
        self,
        user_id: str,
        tier: EntitlementTier,
        features: Optional[List[str]] = None,
        tenant_id: str = "default_tenant",
        expires_at: Optional[datetime] = None,
    ) -> LicenseKey:
        lic = LicenseKey(
            user_id=user_id,
            tenant_id=tenant_id,
            tier=tier,
            features=features or [],
            expires_at=expires_at,
        )
        payload = {
            "key_id": lic.key_id,
            "user_id": lic.user_id,
            "tenant_id": lic.tenant_id,
            "tier": lic.tier.value,
            "features": lic.features,
            "issued_at": lic.issued_at.isoformat(),
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        }
        lic.signature = self._sign_payload(payload)
        return lic

    def verify_license(self, license_key: LicenseKey) -> bool:
        """Verifies signature integrity and expiration status."""
        payload = {
            "key_id": license_key.key_id,
            "user_id": license_key.user_id,
            "tenant_id": license_key.tenant_id,
            "tier": license_key.tier.value,
            "features": license_key.features,
            "issued_at": license_key.issued_at.isoformat(),
            "expires_at": license_key.expires_at.isoformat() if license_key.expires_at else None,
        }
        expected_sig = self._sign_payload(payload)
        if not hmac.compare_digest(expected_sig, license_key.signature):
            return False

        if license_key.expires_at and utc_now() > license_key.expires_at:
            return False

        return True

    def check_entitlement(self, license_key: LicenseKey, required_tier: str, feature: Optional[str] = None) -> bool:
        """Validates if the provided license allows access to a tier or feature."""
        if not self.verify_license(license_key):
            return False

        tier_hierarchy = {
            EntitlementTier.FREE: 1,
            EntitlementTier.PRO: 2,
            EntitlementTier.ENTERPRISE: 3,
        }
        req_tier_enum = EntitlementTier(required_tier.lower())
        if tier_hierarchy.get(license_key.tier, 0) < tier_hierarchy.get(req_tier_enum, 0):
            return False

        if feature and feature not in license_key.features and license_key.tier != EntitlementTier.ENTERPRISE:
            return False

        return True
