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
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger("control.identity.openfga")


@dataclass
class RelationshipTuple:
    """Canonical Google Zanzibar relationship tuple: (user, relation, object)."""
    user: str         # e.g., "user:alice", "agent:bot_1", "user:*"
    relation: str     # e.g., "owner", "editor", "viewer", "member", "admin"
    object: str       # e.g., "document:123", "memory:alice", "organization:acme"
    condition: Optional[Dict[str, Any]] = None
    expires_at: Optional[float] = None


CANONICAL_OPENFGA_MODEL: Dict[str, Any] = {
    "schema_version": "1.1",
    "type_definitions": [
        {"type": "user", "relations": {}},
        {
            "type": "document",
            "relations": {
                "owner": {"this": {}},
                "editor": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "owner"}}]}},
                "viewer": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "editor"}}]}},
                "can_share": {"computedUserset": {"relation": "owner"}},
                "can_edit": {"computedUserset": {"relation": "editor"}},
                "can_view": {"computedUserset": {"relation": "viewer"}},
            },
            "metadata": {
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "editor": {"directly_related_user_types": [{"type": "user"}]},
                    "viewer": {"directly_related_user_types": [{"type": "user"}]},
                }
            },
        },
        {
            "type": "memory",
            "relations": {
                "owner": {"this": {}},
                "admin": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "owner"}}]}},
                "read": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "admin"}}]}},
                "write": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "admin"}}]}},
            },
            "metadata": {
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "read": {"directly_related_user_types": [{"type": "user"}]},
                    "write": {"directly_related_user_types": [{"type": "user"}]},
                }
            },
        },
        {
            "type": "organization",
            "relations": {
                "admin": {"this": {}},
                "member": {"union": {"child": [{"this": {}}, {"computedUserset": {"relation": "admin"}}]}},
                "can_create_agent": {"computedUserset": {"relation": "member"}},
                "can_delete_agent": {"computedUserset": {"relation": "admin"}},
            },
            "metadata": {
                "relations": {
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "member": {"directly_related_user_types": [{"type": "user"}]},
                }
            },
        },
        {
            "type": "agent",
            "relations": {
                "created_by": {"this": {}},
                "acts_for": {"computedUserset": {"relation": "created_by"}},
            },
            "metadata": {
                "relations": {
                    "created_by": {"directly_related_user_types": [{"type": "user"}]},
                }
            },
        },
    ],
}


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
        api_key: Optional[str] = None,
        _defer_prod_check: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.store_id = store_id
        self.api_key = api_key or os.getenv("OPENFGA_API_KEY")
        self._client: Optional[Any] = None
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("openfga")
        )

        # Internal graph store for hermetic / offline execution and immediate verification
        self._tuples: Set[Tuple[str, str, str]] = set()  # (user, relation, object)
        self._tuple_conditions: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._delegations: Dict[str, DelegationGrant] = {}  # delegation_id -> grant
        self._store_initialized: bool = False

        if not _defer_prod_check and self.adapter_mode == "live":
            self._ensure_live_backend()

    def _http_client(self):
        """Return a cached httpx.Client bound to self.api_url with 5-second timeout."""
        if self._client is None or self._client.is_closed:
            import httpx
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.Client(
                base_url=self.api_url,
                headers=headers,
                timeout=5.0,
            )
        return self._client

    def _ensure_live_backend(self) -> None:
        """Verify live OpenFGA connection in live mode."""
        if self.adapter_mode != "live":
            return
        try:
            resp = self._http_client().get("/healthz", timeout=2.0)
            if resp.status_code not in (200, 204):
                fail_closed_in_production(
                    "openfga",
                    f"OpenFGA server returned HTTP {resp.status_code}",
                )
        except ProductionSafetyError:
            raise
        except Exception as exc:
            fail_closed_in_production(
                "openfga",
                f"Live OpenFGA server at {self.api_url} is unreachable: {exc}",
                cause=exc,
            )

        if os.getenv("CI_TEST_MODE") != "1":
            self._ensure_store_initialized()

    def _ensure_store_initialized(self) -> None:
        """Resolve store by name if needed, and bootstrap canonical authorization model."""
        if self._store_initialized or self.adapter_mode != "live":
            return
        client = self._http_client()
        is_ulid = len(self.store_id) == 26 and self.store_id.isalnum()
        resolved_id = None

        if is_ulid:
            try:
                chk = client.get(f"/stores/{self.store_id}", timeout=3.0)
                if chk.status_code == 200:
                    resolved_id = self.store_id
            except Exception:
                pass

        if not resolved_id:
            try:
                list_resp = client.get("/stores", timeout=5.0)
                if list_resp.status_code == 200:
                    stores = list_resp.json().get("stores", [])
                    for s in stores:
                        if s.get("name") == self.store_id or s.get("id") == self.store_id:
                            resolved_id = s.get("id")
                            break
            except Exception:
                pass

        if not resolved_id:
            try:
                create_resp = client.post("/stores", json={"name": self.store_id}, timeout=5.0)
                if create_resp.status_code in (200, 201):
                    resolved_id = create_resp.json().get("id")
            except Exception:
                pass

        if resolved_id:
            self.store_id = resolved_id
            try:
                models_resp = client.get(f"/stores/{self.store_id}/authorization-models", timeout=3.0)
                models = models_resp.json().get("authorization_models", []) if models_resp.status_code == 200 else []
                if not models:
                    client.post(f"/stores/{self.store_id}/authorization-models", json=CANONICAL_OPENFGA_MODEL, timeout=5.0)
            except Exception:
                pass

        self._store_initialized = True

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
        self._ensure_live_backend()
        u = self._normalize_id(user, "user")
        o = self._normalize_id(object, "resource")
        key = (u, relation, o)
        self._tuples.add(key)
        if condition or ttl_seconds:
            cond = dict(condition or {})
            if ttl_seconds:
                cond["_exp"] = time.time() + ttl_seconds
            self._tuple_conditions[key] = cond

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            payload = {
                "writes": {
                    "tuple_keys": [
                        {"user": u, "relation": relation, "object": o}
                    ]
                }
            }
            try:
                resp = self._http_client().post(
                    f"/stores/{self.store_id}/write",
                    json=payload,
                    timeout=5.0,
                )
                if resp.status_code not in (200, 204):
                    fail_closed_in_production(
                        "openfga",
                        f"OpenFGA write returned HTTP {resp.status_code}: {resp.text}",
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production(
                    "openfga",
                    f"OpenFGA write to {self.api_url} failed: {exc}",
                    cause=exc,
                )

    def delete_tuple(self, user: str, relation: str, object: str) -> None:
        self._ensure_live_backend()
        u = self._normalize_id(user, "user")
        o = self._normalize_id(object, "resource")
        key = (u, relation, o)
        self._tuples.discard(key)
        self._tuple_conditions.pop(key, None)

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            payload = {
                "deletes": {
                    "tuple_keys": [
                        {"user": u, "relation": relation, "object": o}
                    ]
                }
            }
            try:
                resp = self._http_client().post(
                    f"/stores/{self.store_id}/write",
                    json=payload,
                    timeout=5.0,
                )
                if resp.status_code not in (200, 204):
                    fail_closed_in_production(
                        "openfga",
                        f"OpenFGA delete returned HTTP {resp.status_code}: {resp.text}",
                    )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production(
                    "openfga",
                    f"OpenFGA delete to {self.api_url} failed: {exc}",
                    cause=exc,
                )

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
        self._ensure_live_backend()
        u = self._normalize_id(user, "user")
        r = self._normalize_id(resource, "resource")
        res_type = r.split(":")[0]

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                check_body: Dict[str, Any] = {
                    "tuple_key": {
                        "user": u,
                        "relation": action,
                        "object": r,
                    },
                }
                if context is not None:
                    check_body["context"] = context
                resp = self._http_client().post(
                    f"/stores/{self.store_id}/check",
                    json=check_body,
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    return bool(resp.json().get("allowed", False))
                fail_closed_in_production(
                    "openfga",
                    f"OpenFGA check returned HTTP {resp.status_code}: {resp.text}",
                )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("openfga", f"OpenFGA check failed: {exc}", cause=exc)

        # 1. Check for Active Delegations
        import fnmatch
        for grant in self._delegations.values():
            if grant.delegatee == u and grant.is_valid():
                if action in grant.capabilities or "*" in grant.capabilities:
                    if (
                        grant.resource_pattern == "*"
                        or grant.resource_pattern in r
                        or fnmatch.fnmatch(r, grant.resource_pattern)
                    ):
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
        self._ensure_live_backend()
        u = self._normalize_id(user, "user")

        if self.adapter_mode == "live" and not os.getenv("CI_TEST_MODE") == "1":
            try:
                resp = self._http_client().post(
                    f"/stores/{self.store_id}/list-objects",
                    json={
                        "user": u,
                        "relation": relation,
                        "type": object_type,
                    },
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    objs = resp.json().get("objects", [])
                    return sorted(list(objs))
                fail_closed_in_production(
                    "openfga",
                    f"OpenFGA list-objects returned HTTP {resp.status_code}: {resp.text}",
                )
            except ProductionSafetyError:
                raise
            except Exception as exc:
                fail_closed_in_production("openfga", f"OpenFGA list-objects failed: {exc}", cause=exc)

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

