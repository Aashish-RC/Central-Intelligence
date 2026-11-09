"""SSO Federation & Automated SCIM User Provisioning (Layer 12: IAM, Task 12.7).

Features:
- 12.30: Enterprise SSO federation with workplace suites (Google Workspace, Microsoft 365)
- 12.31: Sector-specific and government identity federation (eAuth, GovID, Login.gov)
- 12.32: Automated user provisioning and deprovisioning via SCIM 2.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from control.identity.keycloak_adapter import KeycloakAdapter, TokenResponse

logger = logging.getLogger("control.identity.federation")


class FederationProvider(str, Enum):
    GOOGLE_WORKSPACE = "google_workspace"
    MICROSOFT_365 = "microsoft_365"
    OKTA = "okta"
    GOV_LOGIN = "gov_login"


@dataclass
class SCIMUserRequest:
    """SCIM 2.0 User resource representation for automated directory sync."""
    user_name: str
    email: str
    first_name: str
    last_name: str
    external_id: Optional[str] = None
    active: bool = True
    roles: List[str] = field(default_factory=lambda: ["user"])


class FederationManager:
    """Orchestrates enterprise SSO authentication and automated SCIM identity lifecycle."""

    def __init__(self, keycloak_adapter: Optional[KeycloakAdapter] = None):
        self.keycloak = keycloak_adapter or KeycloakAdapter()
        self._scim_external_map: Dict[str, str] = {}  # external_id -> user_id

    def handle_workplace_sso_callback(
        self,
        provider: FederationProvider,
        external_user_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        tenant_id: str = "default",
    ) -> TokenResponse:
        """Handles SSO login callback with Just-In-Time (JIT) auto-provisioning (12.30, 12.31)."""
        full_name = f"{first_name or ''} {last_name or ''}".strip() or email.split("@")[0]
        # Delegates to Keycloak federated login
        token_resp = self.keycloak.federated_login(
            provider=provider.value,
            provider_user_id=external_user_id,
            email=email,
            name=full_name,
        )
        return token_resp

    def scim_provision_user(self, tenant_id: str, user_req: SCIMUserRequest) -> Dict[str, Any]:
        """Provisions a new user or syncs attributes via SCIM 2.0 (12.32)."""
        existing_id = self.keycloak._usernames.get(user_req.email) or self.keycloak._usernames.get(user_req.user_name)

        if existing_id:
            user = self.keycloak._users[existing_id]
            user.enabled = user_req.active
            user.roles = set(user_req.roles)
        else:
            user = self.keycloak.register_user(
                username=user_req.user_name,
                email=user_req.email,
            )
            user.enabled = user_req.active
            user.roles = set(user_req.roles)

        if user_req.external_id:
            self._scim_external_map[user_req.external_id] = user.user_id

        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": user.user_id,
            "userName": user.username,
            "active": user.enabled,
            "emails": [{"value": user.email, "primary": True}],
            "meta": {"resourceType": "User", "created": user.created_at},
        }

    def scim_deprovision_user(self, tenant_id: str, identifier: str) -> bool:
        """Deprovisions user via SCIM: disables account and immediately revokes all active tokens."""
        user_id = self._scim_external_map.get(identifier) or self.keycloak._usernames.get(identifier)
        if not user_id or user_id not in self.keycloak._users:
            return False

        user = self.keycloak._users[user_id]
        user.enabled = False

        # Revoke all active tokens associated with this user
        tokens_to_revoke = [
            tok for tok, claims in self.keycloak._active_tokens.items()
            if claims.get("sub") == user_id
        ]
        for t in tokens_to_revoke:
            self.keycloak.revoke_token(t)

        return True

