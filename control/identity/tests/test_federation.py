"""Tests for SSO Federation & Automated SCIM User Provisioning (Task 12.7)."""

import pytest
from control.identity.federation.sso import (
    FederationManager,
    FederationProvider,
    SCIMUserRequest,
)


def test_google_workspace_sso_and_auto_provisioning_acceptance():
    """Acceptance Test: User logs in via Google Workspace; account auto-provisioned."""
    fed_mgr = FederationManager()

    # User logs in with Google Workspace external credentials
    token_resp = fed_mgr.handle_workplace_sso_callback(
        provider=FederationProvider.GOOGLE_WORKSPACE,
        external_user_id="google-sub-987654321",
        email="elena.rostova@enterprise-domain.com",
        first_name="Elena",
        last_name="Rostova",
        tenant_id="tenant-enterprise",
    )

    # 1. Verify access token issued
    assert token_resp.access_token is not None
    assert token_resp.token_type == "Bearer"

    # 2. Verify account was automatically provisioned in Keycloak
    user_id = fed_mgr.keycloak._usernames.get("elena.rostova@enterprise-domain.com")
    assert user_id is not None
    user = fed_mgr.keycloak._users[user_id]
    assert user.email == "elena.rostova@enterprise-domain.com"
    assert user.social_links.get(FederationProvider.GOOGLE_WORKSPACE.value) == "google-sub-987654321"

    # 3. Verify token validation works
    claims = fed_mgr.keycloak.verify_token(token_resp.access_token)
    assert claims["sub"] == user.user_id
    assert claims["auth_method"] == "sso:google_workspace"


def test_scim_automated_provisioning_and_deprovisioning():
    """Validates SCIM 2.0 automated directory lifecycle."""
    fed_mgr = FederationManager()

    scim_req = SCIMUserRequest(
        user_name="david_dev",
        email="david@acme.org",
        first_name="David",
        last_name="Miller",
        external_id="okta-usr-4412",
        active=True,
        roles=["user", "developer"],
    )

    # 1. SCIM Provision
    scim_resp = fed_mgr.scim_provision_user("tenant-acme", scim_req)
    assert scim_resp["active"] is True
    assert scim_resp["userName"] == "david_dev"

    # Issue token for David
    tokens = fed_mgr.keycloak.issue_tokens(user_id=scim_resp["id"])
    assert fed_mgr.keycloak.verify_token(tokens.access_token) is not None

    # 2. SCIM Deprovision (e.g. employee offboarded)
    success = fed_mgr.scim_deprovision_user("tenant-acme", "okta-usr-4412")
    assert success is True

    # User is disabled and existing tokens are revoked
    user = fed_mgr.keycloak._users[scim_resp["id"]]
    assert user.enabled is False

    with pytest.raises(PermissionError, match="revoked"):
        fed_mgr.keycloak.verify_token(tokens.access_token)

