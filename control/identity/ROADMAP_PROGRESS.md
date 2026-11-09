# Layer 12: Identity & Access Management — Feature Roadmap Progress & Checkpoint Log

> **Subsystem Core:** Python (FastAPI, Keycloak, OpenFGA Zanzibar ReBAC, Infisical) + TypeScript Bridges  
> **Status Standard:** Verified against functional test suites.  
> **Test Suite:** `control/identity/tests/`

---

## 1. Feature Status Table

| Feature ID | Feature Name | Status | License Treatment | Reviewed by Human | Verification Evidence |
|:---|:---|:---:|:---|:---:|:---|
| **12.01** | Password Authentication & Strong Policy Enforcement | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.02** | Passwordless Passkeys (WebAuthn / FIDO2) | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.03** | Multi-Factor Authentication (MFA / TOTP) | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.04** | Social Login Federation (Google, GitHub, Microsoft) | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.05** | Enterprise SSO (SAML 2.0 / OIDC) | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.06** | OAuth 2.1 & OpenID Connect Authorization Server | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.07** | Machine-to-Brain Scoped API Keys | **built** | Own implementation | no | `tests/test_keycloak.py` |
| **12.08** | Token Lifecycle (Issue, Introspect, Refresh, Revoke) | **built** | Adapted (Apache-2.0 - Keycloak) / Own | no | `tests/test_keycloak.py` |
| **12.09** | Role-Based Access Control (RBAC) | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.10** | Attribute-Based Access Control (ABAC & Context-Aware) | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.11** | Per-Capability Permissions | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.12** | Per-App Permissions & Scoping | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.13** | Entitlement-Based Access Control | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.14** | Externalized ReBAC Policy Engine (Google Zanzibar) | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.15** | Delegated Access with Scoped Expiring Rights | **built** | Adapted (Apache-2.0 - OpenFGA) | no | `tests/test_openfga.py` |
| **12.16** | Distinct Identity for Every Agent and Bot | **built** | Own implementation | no | `tests/test_agent_identity.py` |
| **12.17** | Scoped, Short-Lived Agent Credentials | **built** | Own implementation | no | `tests/test_agent_identity.py` |
| **12.18** | Attribution of Action to Agent & Parent User | **built** | Own implementation | no | `tests/test_agent_identity.py` |
| **12.19** | Agent-to-Agent Mutual Authentication | **built** | Own implementation | no | `tests/test_agent_identity.py` |
| **12.20** | Multi-Tenant Data & Execution Isolation | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.21** | Per-Tenant Dedicated Encryption Keys | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.22** | Per-Tenant Model Policy Routing | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.23** | Per-Tenant Safety Guardrails Configuration | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.24** | Per-Tenant Rate Limits & Quotas | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.25** | Tenant Lifecycle Management (Create, Suspend, Delete) | **built** | Own implementation | no | `tests/test_tenancy.py` |
| **12.26** | App-Level API Keys | **built** | Own implementation | no | `tests/test_app_scope.py` |
| **12.27** | App-Level Rate Limiting | **built** | Own implementation | no | `tests/test_app_scope.py` |
| **12.28** | App-Level Data Isolation | **built** | Own implementation | no | `tests/test_app_scope.py` |
| **12.29** | App-Level Capability Scoping | **built** | Own implementation | no | `tests/test_app_scope.py` |
| **12.30** | SSO with Workplace Suites (Google, Microsoft 365) | pending | Own implementation | no | `tests/test_federation.py` |
| **12.31** | Sector & Government Identity Systems | pending | Own implementation | no | `tests/test_federation.py` |
| **12.32** | Automated User Provisioning/Deprovisioning (SCIM) | pending | Own implementation | no | `tests/test_federation.py` |
| **12.33** | Provider-Key Vault for User-Supplied Keys (BYOK) | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.34** | External Secret Manager Integration | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.35** | Zero-Downtime Secret Rotation | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.36** | Secret Access Auditing | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.37** | Per-Tenant and Per-App Secret Scoping | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.38** | Dynamic Secret Injection into Running Services | **built** | Adapted (MIT - Infisical) | no | `tests/test_infisical.py` |
| **12.39** | Session Management & Device Enumeration | pending | Own implementation | no | `tests/test_sessions.py` |
| **12.40** | Administrative Forced Session Revocation | pending | Own implementation | no | `tests/test_sessions.py` |
| **12.41** | Identity Audit Log with L10 Merkle Ledger Bridge | pending | Own implementation | no | `tests/test_sessions.py` |
| **12.42** | Account Recovery (Lost Password, Passkey, Device) | pending | Own implementation | no | `tests/test_lifecycle.py` |
| **12.43** | Account Merging | pending | Own implementation | no | `tests/test_lifecycle.py` |
| **12.44** | Account Closure & 30-Day Grace Period | pending | Own implementation | no | `tests/test_lifecycle.py` |
| **12.45** | Financial Authority Bridge (Spend Limits, Approvals) | pending | Own implementation | no | `tests/test_financial_bridge.py` |
| **12.46** | Operator Console (Inspect, Pause, Override Agents) | pending | Own implementation | no | `tests/test_operator.py` |
| **12.47** | Audited Support Impersonation | pending | Own implementation | no | `tests/test_operator.py` |

---

## 2. OSS Integration Reference

| OSS Tool | Repository URL | License | Purpose & Justification |
|:---|:---|:---:|:---|
| **Keycloak** | [https://github.com/keycloak/keycloak](https://github.com/keycloak/keycloak) | Apache-2.0 | Enterprise IAM, passkeys, WebAuthn, OAuth 2.1, and SSO federation. |
| **OpenFGA** | [https://github.com/openfga/openfga](https://github.com/openfga/openfga) | Apache-2.0 | Google Zanzibar Relationship-Based Access Control (ReBAC) engine. |
| **Infisical** | [https://github.com/Infisical/infisical](https://github.com/Infisical/infisical) | MIT | Enterprise secret manager, BYOK vault, and rotation lifecycle. |
