"""Per-App Data Sandboxing (L15 Data & Messaging - Tasks 15.34, 15.35).

Provides virtual schema isolation and granular access grants between apps.
Apps cannot access, query, or mutate another app's isolated datastore
unless explicit, time-bounded permission grants have been authorized.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when an app attempts unauthorized access to another app's sandbox."""
    pass


@dataclass
class AccessGrant:
    """Explicit cross-app authorization grant."""
    grantor_app_id: str
    grantee_app_id: str
    collection: str
    permissions: Set[str] = field(default_factory=lambda: {"read"})
    granted_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None

    def is_valid(self, requested_perm: str = "read") -> bool:
        if requested_perm not in self.permissions:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return True


@dataclass
class SandboxConfig:
    """Configuration for AppSandbox."""
    strict_mode: bool = True
    audit_enabled: bool = True


class AppSandbox:
    """Virtual schema manager providing per-app datastore isolation."""

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        self.config = config or SandboxConfig()
        # app_id -> collection -> record_id -> document
        self._stores: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
        # (grantor, grantee, collection) -> AccessGrant
        self._grants: Dict[tuple[str, str, str], AccessGrant] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def _ensure_schema(self, app_id: str, collection: str) -> None:
        if app_id not in self._stores:
            self._stores[app_id] = {}
        if collection not in self._stores[app_id]:
            self._stores[app_id][collection] = {}

    def _verify_access(
        self,
        target_app_id: str,
        requester_app_id: str,
        collection: str,
        action: str = "read",
    ) -> None:
        """Verify whether requester has permission to target app's collection."""
        if requester_app_id == target_app_id:
            return  # Apps always have full access to their own sandbox

        grant_key = (target_app_id, requester_app_id, collection)
        grant = self._grants.get(grant_key)

        # Also check wildcard collection grant "*"
        if not grant or not grant.is_valid(action):
            wildcard_grant = self._grants.get((target_app_id, requester_app_id, "*"))
            if wildcard_grant and wildcard_grant.is_valid(action):
                grant = wildcard_grant

        if not grant or not grant.is_valid(action):
            if self.config.audit_enabled:
                self._audit_log.append({
                    "action": action,
                    "target_app_id": target_app_id,
                    "requester_app_id": requester_app_id,
                    "collection": collection,
                    "status": "DENIED",
                    "timestamp": time.time(),
                })
            raise PermissionDeniedError(
                f"Access denied: App '{requester_app_id}' cannot {action} '{target_app_id}/{collection}' without grant"
            )

        if self.config.audit_enabled:
            self._audit_log.append({
                "action": action,
                "target_app_id": target_app_id,
                "requester_app_id": requester_app_id,
                "collection": collection,
                "status": "ALLOWED",
                "timestamp": time.time(),
            })

    def grant_cross_app_access(
        self,
        grantor_app_id: str,
        grantee_app_id: str,
        collection: str,
        permissions: Optional[Set[str]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> AccessGrant:
        """Explicitly authorize cross-app access."""
        expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None
        grant = AccessGrant(
            grantor_app_id=grantor_app_id,
            grantee_app_id=grantee_app_id,
            collection=collection,
            permissions=permissions or {"read"},
            expires_at=expires_at,
        )
        self._grants[(grantor_app_id, grantee_app_id, collection)] = grant
        logger.info(
            "Granted access: %s -> %s on %s (perms: %s)",
            grantee_app_id,
            grantor_app_id,
            collection,
            grant.permissions,
        )
        return grant

    def revoke_cross_app_access(
        self,
        grantor_app_id: str,
        grantee_app_id: str,
        collection: str,
    ) -> bool:
        """Revoke a previously granted cross-app authorization."""
        grant_key = (grantor_app_id, grantee_app_id, collection)
        if grant_key in self._grants:
            del self._grants[grant_key]
            return True
        return False

    def insert(
        self,
        app_id: str,
        collection: str,
        record_id: str,
        data: Dict[str, Any],
        requester_app_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or replace record in app's isolated virtual schema."""
        requester = requester_app_id or app_id
        self._verify_access(app_id, requester, collection, action="write")
        self._ensure_schema(app_id, collection)
        self._stores[app_id][collection][record_id] = copy.deepcopy(data)
        return self._stores[app_id][collection][record_id]

    def get(
        self,
        app_id: str,
        collection: str,
        record_id: str,
        requester_app_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve record from app's schema with security checks."""
        requester = requester_app_id or app_id
        self._verify_access(app_id, requester, collection, action="read")

        app_store = self._stores.get(app_id, {})
        col_store = app_store.get(collection, {})
        record = col_store.get(record_id)
        return copy.deepcopy(record) if record is not None else None

    def query(
        self,
        app_id: str,
        collection: str,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
        requester_app_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query records from app's schema with permission enforcement."""
        requester = requester_app_id or app_id
        self._verify_access(app_id, requester, collection, action="read")

        app_store = self._stores.get(app_id, {})
        col_store = app_store.get(collection, {})

        results = []
        for doc in col_store.values():
            if filter_fn is None or filter_fn(doc):
                results.append(copy.deepcopy(doc))
        return results

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Fetch audit log of cross-app requests."""
        return list(self._audit_log)

