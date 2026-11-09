# Layer 12: Identity & Access Management (IAM)

Multi-tenant organization hierarchies, passwordless passkeys, enterprise SSO, OAuth 2.1, Google Zanzibar ReBAC authorization (OpenFGA), and zero-downtime secret vaults (Infisical).

---

## 1. Core Modules

### `control.identity.keycloak_adapter` (Keycloak Integration)
- Password policy and hashing.
- Passwordless passkeys (WebAuthn / FIDO2).
- Multi-factor authentication (MFA / TOTP).
- Social login and enterprise SSO (SAML 2.0 / OIDC).
- OAuth 2.1 token issuance, refresh rotation, and revocation.
- Brain API keys for application-to-brain integration.

### `control.identity.openfga_adapter` (OpenFGA / Google Zanzibar ReBAC)
- Fine-grained relationship-based access control.
- Role, attribute, capability, and entitlement checks.
- Delegated access with short-lived scoped rights.
- **Unblocks DEF-01 (L2 Memory Access Control)** and **DEF-02 (L3 Permission-Filtered Retrieval)**.

### `control.identity.secrets` (Infisical Vault)
- Bring-Your-Own-Key (BYOK) provider vaults.
- Zero-downtime rotation and access auditing.
- Per-tenant and per-app scoped secret injection.

### `control.identity.agent`
- Unique identities for autonomous agents and sub-agents.
- Short-lived scoped credentials and parent user attribution.
- Mutual agent-to-agent authentication.

### `control.identity.tenancy`
- Multi-tenant data and execution isolation.
- Per-tenant encryption keys, model policies, guardrails, and rate limits.

### `control.identity.financial`
- Bridges directly to L5 Financial Authority Guard for transaction approvals, spend thresholds, and receipts.

### `control.identity.operator`
- Administrative controls to pause/override agent actions.
- Tamper-evident audited support impersonation.

---

## 2. Docker Services

Registered in `docker-compose.yml`:
- `keycloak`: `quay.io/keycloak/keycloak:latest` on port `8085:8080`
- `openfga`: `openfga/openfga:latest` on ports `8081` (HTTP) and `8082` (gRPC)
- `infisical`: `infisical/infisical:latest` on port `8083`

---

## 3. Testing

Run L12 tests with:
```bash
python -m pytest control/identity/tests/ -v
```
