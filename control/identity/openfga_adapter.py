"""OpenFGA Google Zanzibar ReBAC Authorization Adapter (Layer 12: Identity & Access Management, Task 12.2).

Features:
- 12.09: Role-based access control (RBAC) via relationship tuples
- 12.10: Attribute-based & context-aware access (time, IP, device, status)
- 12.11: Per-capability permissions
- 12.12: Per-app permissions and isolation
- 12.13: Entitlement-based access
- 12.14: Externalized policy engine (Zanzibar tuple store)
- 12.15: Delegated access with scoped, expiring rights
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.identity.openfga")


@dataclass
class RelationshipTuple:
    """Canonical Google Zanzibar relationship tuple: (user, relation, object)."""
    user: str         # e.g., "user:alice", "agent:bot_1", "user:*"
    relation: str     # e.g., "owner", "editor", "viewer", "member", "admin"
    object: str       # e.g., "document:123", "memory:alice", "organization:acme"
    condition: Optional[Dict[str, Any]] = None
    expires_at: Optional[float] = None


@dataclass
class DelegationGrant:
    """Scoped, expiring delegated authorization for sub-agents or third-party apps."""
    delegation_id: str
    delegator: str
    delegatee: str
    capabilities: Set[str]
    resource_pattern: str
    expires_at: float
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_valid(self) -> bool:
        return time.time() < self.expires_at


class OpenFGAAdapter:
    """Google Zanzibar-style ReBAC authorization engine supporting OpenFGA semantics."""

    def __init__(
        self,
        api_url: str = "http://localhost:8081",
        store_id: str = "central-intelligence-store",
    ):
        self.api_url = api_url
        self.store_id = store_id

        # Internal graph store for hermetic / offline execution and immediate verification
        self._tuples: Set[Tuple[str, str, str]] = set()  # (user, relation, object)
        self._tuple_conditions: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._delegations: Dict[str, DelegationGrant] = {}  # delegation_id -> grant

    def _normalize_id(self, entity: str, default_type: str) -> str:
        if ":" in entity:
            return entity
        return f"{default_type}:{entity}"

    def write_tuple(
        self,
        user: str,
        relation: str,
        object: str,
        condition: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Writes relationship tuple (user, relation, object)."""
        u = self._normalize_id(user, "user")
        o = self._normalize_id(object, "resource")
        key = (u, relation, o)
        self._tuples.add(key)
        if condition or ttl_seconds:
            cond = dict(condition or {})
            if ttl_seconds:
                cond["_exp"] = time.time() + ttl_seconds
            self._tuple_conditions[key] = cond

    def delete_tuple(self, user: str, relation: str, object: str) -> None:
        u = self._normalize_id(user, "user")
        o = self._normalize_id(object, "resource")
        key = (u, relation, o)
        self._tuples.discard(key)
        self._tuple_conditions.pop(key, None)

    def has_direct_relation(self, user: str, relation: str, object: str, context: Optional[Dict[str, Any]] = None) -> bool:
        key = (user, relation, object)
        if key not in self._tuples:
            # Check wildcard "user:*"
            if ("user:*", relation, object) in self._tuples:
                key = ("user:*", relation, object)
            else:
                return False

        # Check conditions & expiry
        if key in self._tuple_conditions:
            cond = self._tuple_conditions[key]
            if "_exp" in cond and time.time() > cond["_exp"]:
                # Expired tuple
                self._tuples.discard(key)
                del self._tuple_conditions[key]
                return False

            if context:
                for k, v in cond.items():
                    if k.startswith("_"):
                        continue
                    if context.get(k) != v:
                        return False

        return True

    def check_permission(
        self,
        user: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluates whether actor has permission on resource according to Zanzibar model rules."""
        u = self._normalize_id(user, "user")
        r = self._normalize_id(resource, "resource")
        res_type = r.split(":")[0]

        # 1. Check for Active Delegations
        for grant in self._delegations.values():
            if grant.delegatee == u and grant.is_valid():
                if action in grant.capabilities or "*" in grant.capabilities:
                    if grant.resource_pattern == "*" or grant.resource_pattern in r:
                        return True

        # 2. Document Hierarchy Evaluation
        # Schema:
        # can_edit = editor or owner
        # can_view = viewer or editor or owner
        # can_share = owner
        if res_type == "document":
            is_owner = self.has_direct_relation(u, "owner", r, context)
            if action == "owner" and is_owner:
                return True
            if action == "can_share" and is_owner:
                return True

            is_editor = is_owner or self.has_direct_relation(u, "editor", r, context)
            if action == "editor" and is_editor:
                return True
            if action == "can_edit" and is_editor:
                return True

            is_viewer = is_editor or self.has_direct_relation(u, "viewer", r, context)
            if action in ("viewer", "can_view") and is_viewer:
                return True

        # 3. Memory Hierarchy Evaluation (for L2 DEF-01)
        # Schema:
        # read = direct "read" or "admin" or "owner"
        # write = direct "write" or "admin" or "owner"
        if res_type == "memory":
            if self.has_direct_relation(u, "admin", r, context) or self.has_direct_relation(u, "owner", r, context):
                return True
            if self.has_direct_relation(u, action, r, context):
                return True

        # 4. Organization Hierarchy Evaluation
        # Schema:
        # can_create_agent = admin or member
        # can_delete_agent = admin
        if res_type == "organization":
            is_admin = self.has_direct_relation(u, "admin", r, context)
            if action in ("admin", "can_delete_agent") and is_admin:
                return True
            is_member = is_admin or self.has_direct_relation(u, "member", r, context)
            if action in ("member", "can_create_agent") and is_member:
                return True

        # 5. Agent Delegation Hierarchy
        # acts_for: agent acts for user if user created it or granted delegation
        if res_type == "agent" and action == "acts_for":
            if self.has_direct_relation(u, "created_by", r, context):
                return True

        # 6. Generic direct relation fallback
        return self.has_direct_relation(u, action, r, context)

    def batch_check(
        self,
        checks: List[Tuple[str, str, str]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[bool]:
        return [self.check_permission(u, a, r, context) for u, a, r in checks]

    def list_objects(self, user: str, relation: str, object_type: str) -> List[str]:
        """Returns all objects of object_type where user has relation/action."""
        results = set()
        prefix = f"{object_type}:"
        for _, _, obj in self._tuples:
            if obj.startswith(prefix) and self.check_permission(user, relation, obj):
                results.add(obj)
        return sorted(list(results))

    def grant_delegation(
        self,
        delegator: str,
        delegatee: str,
        capabilities: List[str],
        resource_pattern: str = "*",
        ttl_seconds: int = 900,
    ) -> DelegationGrant:
        """Creates a short-lived delegated capability grant (12.15)."""
        d_id = f"del-{len(self._delegations)+1}"
        grant = DelegationGrant(
            delegation_id=d_id,
            delegator=self._normalize_id(delegator, "user"),
            delegatee=self._normalize_id(delegatee, "agent"),
            capabilities=set(capabilities),
            resource_pattern=resource_pattern,
            expires_at=time.time() + ttl_seconds,
        )
        self._delegations[d_id] = grant
        return grant


# Global default instance
default_openfga_adapter = OpenFGAAdapter()
