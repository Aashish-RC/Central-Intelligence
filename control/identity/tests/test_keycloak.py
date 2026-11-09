"""Tests for Keycloak Enterprise IAM Adapter (Task 12.1)."""

import pytest
from control.identity.keycloak_adapter import KeycloakAdapter


def test_keycloak_user_passkey_and_api_call_acceptance():
    """Acceptance Test: User can register, login with passkey, get JWT token, use it to call the API."""
    adapter = KeycloakAdapter()

    # 1. User registration with strong password
    user = adapter.register_user(
        username="alice_researcher",
        email="alice@central-intelligence.org",
        password="SuperSecretPassword2026!",
    )
    assert user.user_id.startswith("usr-")
    assert user.username == "alice_researcher"

    # 2. Register passkey (WebAuthn / FIDO2)
    cred_id = "cred-fido2-yubikey-01"
    passkey = adapter.register_passkey(
        user_id=user.user_id,
        credential_id=cred_id,
        public_key_pem="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...\n-----END PUBLIC KEY-----",
        device_name="Alice YubiKey 5C",
    )
    assert passkey["credential_id"] == cred_id

    # 3. Login with passkey -> get JWT token response
    token_resp = adapter.authenticate_passkey(
        credential_id=cred_id,
        client_data_json='{"type":"webauthn.get"}',
        authenticator_data=b"authdata",
        signature=b"sig",
    )
    assert token_resp.access_token.startswith("jwt_acc_")
    assert token_resp.token_type == "Bearer"

    # 4. Use token to call the API / verify access claims
    claims = adapter.verify_token(token_resp.access_token)
    assert claims["sub"] == user.user_id
    assert claims["auth_method"] == "webauthn"
    assert "brain:invoke" in claims["scope"]


def test_password_policy_and_authentication():
    """Validates strong password policy enforcement and credential verification."""
    adapter = KeycloakAdapter()

    # Weak password rejected
    with pytest.raises(ValueError, match="strong policy"):
        adapter.register_user("bob", "bob@example.com", "weak")

    # Valid password accepted
    user = adapter.register_user("bob", "bob@example.com", "Secure#Password123!")

    # Login succeeds
    tokens = adapter.authenticate_password("bob", "Secure#Password123!")
    assert tokens.access_token is not None

    # Bad password fails
    with pytest.raises(PermissionError, match="Invalid username or password"):
        adapter.authenticate_password("bob", "WrongPassword!")


def test_token_refresh_and_revocation():
    """Validates token refresh rotation and explicit token revocation."""
    adapter = KeycloakAdapter()
    tokens = adapter.issue_tokens(user_id="user-123")

    # Verify active
    claims = adapter.verify_token(tokens.access_token)
    assert claims["sub"] == "user-123"

    # Refresh token rotation
    refreshed = adapter.refresh_access_token(tokens.refresh_token)
    assert refreshed.access_token != tokens.access_token

    # Old token revoked
    with pytest.raises(PermissionError, match="revoked"):
        adapter.verify_token(tokens.access_token)

    # New token valid
    assert adapter.verify_token(refreshed.access_token)["sub"] == "user-123"

    # Explicit revocation
    adapter.revoke_token(refreshed.access_token)
    with pytest.raises(PermissionError, match="revoked"):
        adapter.verify_token(refreshed.access_token)


def test_brain_api_keys():
    """Validates brain API key creation, verification, and revocation."""
    adapter = KeycloakAdapter()

    raw_key, record = adapter.create_api_key(
        user_id="service_acc_01",
        name="CI Workflow Key",
        tenant_id="tenant_alpha",
    )

    assert raw_key.startswith("bk_")

    verified = adapter.verify_api_key(raw_key)
    assert verified.user_id == "service_acc_01"
    assert verified.tenant_id == "tenant_alpha"

    # Revoke
    record.revoked = True
    with pytest.raises(PermissionError, match="revoked"):
        adapter.verify_api_key(raw_key)

