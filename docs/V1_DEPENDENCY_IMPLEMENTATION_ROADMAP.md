# CENTRAL INTELLIGENCE V1 — DEPENDENCY IMPLEMENTATION ROADMAP & DECISION REGISTER

**Author:** Principal Software Architect, Platform Engineering Lead & QA Lead  
**Scope:** Actionable Implementation Plan, Prioritized Task Inventory, and Decision Register  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **ACTIVE IMPLEMENTATION ROADMAP — PENDING EXPLICIT APPROVALS**  

---

## 1. Decision Register

The Decision Register records the formal status of all architectural and implementation decisions for Central Intelligence V1:

### 1.1 Approved Architectural Principles (Approved & In Effect)
1. **Capability Decoupling:** Mandatory platform capabilities must not be unnecessarily tied to specific third-party products.
2. **Engine Replaceability:** External engines must remain replaceable wherever technically feasible.
3. **Deployment Profiles:** CI must support Lite, Standard, and Enterprise deployment profiles.
4. **Modularity & Hot-Swapping:** Components should be independently configurable, upgradeable, and hot-swappable where contracts and state semantics permit.
5. **Core Independence:** Optional integrations must not prevent unrelated core capabilities from functioning.
6. **Uncompromised Security:** Mandatory security, isolation, authorization, persistence, and reliability requirements cannot be weakened.
7. **Test Availability:** Provider-specific tests must remain available even when providers become optional.
8. **Customer Data Protection:** Existing customer configurations and data must be protected during migration.
9. **Zero Paid Spending:** Zero mandatory paid spending remains a fundamental constraint.
10. **Enterprise Optionality:** Enterprise customers must retain the option to use supported external engines.

### 1.2 Proposed Implementation Changes (Awaiting Approval)
- **PROP-01:** Implement `NativeSqlZanzibarProvider` as a lightweight embedded authorization engine in SQLite/PostgreSQL alongside OpenFGA.
- **PROP-02:** Implement `NativeEnvelopeVaultProvider` as an embedded AES-256-GCM secret vault in SQLite/PostgreSQL alongside Infisical.
- **PROP-03:** Implement `NativeDurableOrchestrator` with SQLite WAL checkpoints inside `OrchestratorBridge` for standalone workflow durability without Temporal.
- **PROP-04:** Consolidate auxiliary PostgreSQL databases (`openfga`, `infisical`, `lago`, `openmeter`) into `central-supabase-db` logical databases.
- **PROP-05:** Consolidate auxiliary Redis instances into `central-valkey` using logical database indices 0 through 4.
- **PROP-06:** Transition release gates from single-engine vendor requirements to the Four-Tier test framework once replacement equivalence tests pass.

### 1.3 Changes Requiring Explicit Approval (Gate Hold)
- **GATE-01:** Removal of any service from `docker-compose.yml`.
- **GATE-02:** Modification of default production connection strings in `.env.example` or deployment templates.
- **GATE-03:** Live production database schema migration or consolidation of existing data volumes.
- **GATE-04:** Alteration of authoritative release gates in `docs/CRITICAL_RELEASE_GATE_REPORT.md`.
- **GATE-05:** Provisioning of external cloud servers or paid infrastructure.

### 1.4 Completed and Verified Changes (Verified Live)
- **DONE-01:** Volume-backed durability migration for OpenFGA (`DEF-10`).
- **DONE-02:** Named Docker volume persistence for Supabase PostgreSQL (`DEF-11`).
- **DONE-03:** Bytebase 3.x authenticated CI/CD DDL migration adapter (`DEF-12`).
- **DONE-04:** Infisical Machine Identity Universal Auth adapter fix (`DEF-13`).
- **DONE-05:** 12/12 Container sandbox runtime isolation controls verified live.
- **DONE-06:** Temporal worker crash recovery and event history replay verified live.

### 1.5 Deferred Work (Post-V1.0)
- **DEF-01:** Kubernetes Helm charts and Kustomize production manifests (Deferred to V1.1).
- **DEF-02:** Multi-region active-active database replication (Deferred to V1.2).
- **DEF-03:** WebAssembly (Wasmtime) edge sandboxing runner (Deferred to V1.1).

---

## 2. Prioritized Implementation Roadmap

Tasks are strictly prioritized into four engineering tiers:
- **P0: Security & Correctness**
- **P1: Release Blockers**
- **P2: Resource Optimization**
- **P3: Optional Enterprise Integrations**

---

### Priority P0: Security and Correctness

#### Task P0.1: Formalize Abstract Domain Contracts & Equivalence Test Suites
- **Files Affected:**
  - `control/identity/interfaces.py`
  - `control/identity/secrets/interfaces.py`
  - `control/orchestration/workflow_builder/core/interfaces.py`
  - `control/billing/interfaces.py`
  - `tests/unit/contracts/test_contract_authz_equivalence.py`
  - `tests/unit/contracts/test_contract_secrets_equivalence.py`
  - `tests/unit/contracts/test_contract_workflow_equivalence.py`
- **Dependencies:** None.
- **Acceptance Criteria:** Abstract base classes defined with complete type annotations. Equivalence test suites pass against current live adapters (OpenFGA, Infisical, Temporal).
- **Test Commands:** `pytest tests/unit/contracts/ -v`
- **Expected Resources:** Negligible (<50 MiB RAM, standard CPU).
- **Risks:** Interface divergence between TypeScript reasoning layer and Python control layer.
- **Rollback Plan:** Retain direct adapter imports; no breaking API changes.
- **Effort:** 8h (Optimistic) / 14h (Likely) / 22h (Conservative).
- **Approval Required:** No (Non-destructive interface addition).

#### Task P0.2: Implement Embedded AES-256-GCM Envelope Secret Vault
- **Files Affected:**
  - `control/identity/secrets/envelope_vault.py`
  - `tests/unit/test_envelope_vault.py`
- **Dependencies:** Task P0.1 (`BaseSecretVault`).
- **Acceptance Criteria:** Authenticated encryption using AES-256-GCM, zero plaintext storage in SQLite/Postgres, versioned rotation, SHA-256 Merkle audit trail, process restart durability.
- **Test Commands:** `pytest tests/unit/test_envelope_vault.py -v`
- **Expected Resources:** ~10 MiB RAM, in-process execution.
- **Risks:** Improper IV reuse or key derivation vulnerability.
- **Rollback Plan:** Set `SECRETS_ENGINE=infisical` to use external Infisical daemon.
- **Effort:** 6h / 12h / 20h.
- **Approval Required:** Proposed (Approval required before making it production default).

#### Task P0.3: Implement Native SQLite/PostgreSQL Zanzibar ReBAC Engine
- **Files Affected:**
  - `control/identity/sql_zanzibar.py`
  - `tests/unit/test_sql_zanzibar.py`
- **Dependencies:** Task P0.1 (`BaseAuthorizationEngine`).
- **Acceptance Criteria:** Recursive CTE resolving transitive viewer/editor/owner relationships, group memberships, and scoped delegations in <5ms. Fails closed on error.
- **Test Commands:** `pytest tests/unit/test_sql_zanzibar.py -v`
- **Expected Resources:** In-process SQLite or co-located in PostgreSQL (~15 MiB).
- **Risks:** Infinite recursion on cyclic relationship graphs.
- **Rollback Plan:** Bounded CTE recursion depth limit (16 levels) + fallback to OpenFGA.
- **Effort:** 10h / 18h / 28h.
- **Approval Required:** Proposed (Approval required before making it production default).

---

### Priority P1: Release Blockers

#### Task P1.1: Provision Staging Environment for Remaining S2 Scenarios
- **Target Integrations:** Lago (SC-03), OpenMeter (SC-04), SigNoz (SC-05), LibreChat (SC-11).
- **Files Affected:** `tests/integration/test_compose_stack_e2e.py`
- **Dependencies:** Legitimate 16 GB staging runner (e.g., GitHub Codespace).
- **Acceptance Criteria:** Real containers booted sequentially or concurrently in 16 GB environment; actual HTTP/gRPC requests dispatched; process restart durability confirmed; zero mocks.
- **Test Commands:** `pytest -m requires_provisioned_services tests/integration/test_compose_stack_e2e.py -v`
- **Expected Resources:** 16 GB RAM staging runner, $0.00 spend.
- **Risks:** Rate limits or memory spikes during ClickHouse/Kafka startup.
- **Rollback Plan:** Sequential batch execution (Lago alone, then OpenMeter, then SigNoz).
- **Effort:** 8h / 16h / 32h.
- **Approval Required:** Yes (Approval to activate staging infrastructure).

#### Task P1.2: Reconcile and Formalize Release Gates
- **Files Affected:**
  - `docs/CRITICAL_RELEASE_GATE_REPORT.md`
  - `docs/V1_REVISED_TEST_GATE_IMPLEMENTATION_PLAN.md`
- **Dependencies:** P0.1, P0.2, P0.3, and P1.1.
- **Acceptance Criteria:** Four-Tier test framework formally verified. All Tier 1 and Tier 2 tests pass 100%. Tier 3 optional provider tests cleanly separated.
- **Test Commands:** `pytest -m "tier1_functional or tier2_security" -v`
- **Expected Resources:** Local machine (~1.2 GiB RAM).
- **Risks:** Premature gating relaxation before replacement tests pass.
- **Rollback Plan:** Revert to historical gate definitions if contract equivalence fails.
- **Effort:** 4h / 8h / 14h.
- **Approval Required:** Yes (Explicit architectural sign-off required).

---

### Priority P2: Resource Optimization

#### Task P2.1: Wire PostgreSQL Consolidation Script in Compose
- **Files Affected:**
  - `docker-compose.yml`
  - `compose/postgres/init-multi-db.sh`
- **Dependencies:** Pre-migration verification in staging.
- **Acceptance Criteria:** `central-supabase-db` creates `openfga`, `infisical`, `lago`, `openmeter` logical databases on initialization. Eliminates 5 redundant Postgres containers.
- **Test Commands:** `docker compose up -d supabase-db && docker exec central-supabase-db psql -U postgres -l`
- **Expected Resources:** Saves ~215 MiB RAM.
- **Risks:** Shared database container restart affects all dependent services.
- **Rollback Plan:** Maintain `compose/archive/docker-compose.split-db.yml` for instant fallback.
- **Effort:** 4h / 8h / 14h.
- **Approval Required:** Yes (Explicit approval before updating production compose).

#### Task P2.2: Standardize Cache on Valkey and Purge Non-OSI Redis
- **Files Affected:**
  - `docker-compose.yml`
  - `.env.example`
- **Dependencies:** None.
- **Acceptance Criteria:** Infisical, OpenMeter, and Lago point to `central-valkey` database indices 2, 3, and 4. Purge `redis:7.4.7` (RSALv2/SSPL) and `dragonfly` (BSL) containers.
- **Test Commands:** `python scripts/check_licenses.py` (Must report 0 non-OSI warnings).
- **Expected Resources:** Saves ~87 MiB RAM.
- **Risks:** Cache key collisions if database index isolation is improperly configured.
- **Rollback Plan:** Re-enable isolated Redis containers.
- **Effort:** 4h / 6h / 10h.
- **Approval Required:** Yes (Explicit approval before changing default compose).

---

### Priority P3: Optional Enterprise Integrations

#### Task P3.1: Package Optional Profiles in Compose
- **Files Affected:** `docker-compose.yml`
- **Dependencies:** P2.1, P2.2.
- **Acceptance Criteria:** Services correctly assigned to `['lite']`, `['standard']`, and `['enterprise']` compose profiles. `docker compose --profile lite up` starts only 4 containers.
- **Test Commands:** `docker compose --profile lite config` & `docker compose --profile standard config`
- **Expected Resources:** Lite: ~450 MiB; Standard: ~1,116 MiB; Enterprise: ~7.2 GiB.
- **Risks:** Service startup order dependencies across profiles.
- **Rollback Plan:** Revert profile tags.
- **Effort:** 4h / 8h / 12h.
- **Approval Required:** Yes (Explicit approval before updating compose profiles).

#### Task P3.2: Kamal Deployment Target Integration (When Authorized Target Provided)
- **Files Affected:** `platform_infra/release/ci/kamal_adapter.py`
- **Dependencies:** Authorized staging server with SSH credentials.
- **Acceptance Criteria:** Rolling container swap executed live against target server with health check polling and zero request drops.
- **Test Commands:** `pytest tests/integration/test_compose_stack_e2e.py -k test_kamal_live_deployment`
- **Expected Resources:** External server (2 CPU, 4 GB RAM).
- **Risks:** Inadvertent deployment to wrong IP address.
- **Rollback Plan:** Automated `kamal app rollback`.
- **Effort:** 4h / 8h / 16h.
- **Approval Required:** Yes (Explicit authorization required prior to external SSH connection).
