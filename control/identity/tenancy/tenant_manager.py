"""Multi-Tenant Isolation & Lifecycle Management (Layer 12: IAM, Task 12.5).

Features:
- 12.20: Strict tenant data & execution isolation
- 12.21: Dedicated per-tenant encryption keys (bridges to L15 Data)
- 12.22: Per-tenant model routing policies (bridges to L8 Orchestration)
- 12.23: Per-tenant safety guardrail overrides (bridges to L10 Safety)
- 12.24: Per-tenant rate limiting and quota enforcement
- 12.25: Tenant lifecycle management (create, configure, suspend, delete)
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("control.identity.tenancy")


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class TenantRecord:
    """Enterprise multi-tenant boundary profile."""
    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    encryption_key: str = field(default_factory=lambda: secrets.token_hex(32))  # 256-bit AES key
    model_policy: Dict[str, Any] = field(default_factory=lambda: {"allowed_models": ["claude-3-7-sonnet", "gpt-4o"], "fallback": "ollama"})
    guardrails_policy: Dict[str, Any] = field(default_factory=lambda: {"strict_pii": True, "profanity_filter": True})
    rate_limit_rpm: int = 120
    rate_limit_tpm: int = 100000
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TenantManager:
    """Manages tenant lifecycle, cryptographic keys, model policies, and strict isolation."""

    def __init__(self):
        self._tenants: Dict[str, TenantRecord] = {}
        self._request_counters: Dict[str, List[float]] = {}  # tenant_id -> timestamps of requests

    def create_tenant(
        self,
        name: str,
        tenant_id: Optional[str] = None,
        rate_limit_rpm: int = 120,
        rate_limit_tpm: int = 100000,
        model_policy: Optional[Dict[str, Any]] = None,
        guardrails_policy: Optional[Dict[str, Any]] = None,
    ) -> TenantRecord:
        t_id = tenant_id or f"tnt-{secrets.token_hex(6)}"
        if t_id in self._tenants:
            raise ValueError(f"Tenant with id '{t_id}' already exists")

        tenant = TenantRecord(
            tenant_id=t_id,
            name=name,
            rate_limit_rpm=rate_limit_rpm,
            rate_limit_tpm=rate_limit_tpm,
            model_policy=model_policy or {"allowed_models": ["claude-3-7-sonnet", "gpt-4o"], "fallback": "ollama"},
            guardrails_policy=guardrails_policy or {"strict_pii": True, "profanity_filter": True},
        )
        self._tenants[t_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> TenantRecord:
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.status == TenantStatus.DELETED:
            raise KeyError(f"Tenant '{tenant_id}' not found or deleted")
        return tenant

    def suspend_tenant(self, tenant_id: str) -> TenantRecord:
        tenant = self.get_tenant(tenant_id)
        tenant.status = TenantStatus.SUSPENDED
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        return tenant

    def activate_tenant(self, tenant_id: str) -> TenantRecord:
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            raise KeyError(f"Tenant '{tenant_id}' not found")
        tenant.status = TenantStatus.ACTIVE
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        if tenant_id in self._tenants:
            self._tenants[tenant_id].status = TenantStatus.DELETED
            return True
        return False

    def get_tenant_encryption_key(self, tenant_id: str) -> str:
        """Returns dedicated 256-bit encryption key (12.21)."""
        tenant = self.get_tenant(tenant_id)
        if tenant.status != TenantStatus.ACTIVE:
            raise PermissionError(f"Tenant '{tenant_id}' is not active")
        return tenant.encryption_key

    def check_data_isolation(self, requester_tenant_id: str, resource_owner_tenant_id: str) -> bool:
        """Enforces tenant data boundary; True only if requester and owner match (12.20)."""
        return requester_tenant_id == resource_owner_tenant_id

    def check_rate_limit(self, tenant_id: str) -> bool:
        """Enforces sliding-window rate limit RPM (12.24). Returns True if allowed, False if exceeded."""
        tenant = self.get_tenant(tenant_id)
        if tenant.status != TenantStatus.ACTIVE:
            raise PermissionError(f"Tenant '{tenant_id}' is not active")

        now = time.time()
        window_start = now - 60.0

        timestamps = self._request_counters.setdefault(tenant_id, [])
        # Prune old timestamps
        timestamps = [ts for ts in timestamps if ts > window_start]
        self._request_counters[tenant_id] = timestamps

        if len(timestamps) >= tenant.rate_limit_rpm:
            return False

        timestamps.append(now)
        return True


# Default singleton
default_tenant_manager = TenantManager()

