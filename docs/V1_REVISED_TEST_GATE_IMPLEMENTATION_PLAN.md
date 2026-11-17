# CENTRAL INTELLIGENCE V1 — REVISED TEST GATE IMPLEMENTATION PLAN

**Author:** QA Engineering Lead, Systems Reliability Auditor & Principal Architect  
**Scope:** Actionable Four-Tier Test Gate Matrix, Pytest Categorization, CI/CD Mapping & Transition Governance  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **IMPLEMENTATION-READY PROPOSAL — PENDING FORMAL SIGN-OFF BEFORE ENFORCEMENT**  

---

## 1. Executive Summary & Quality Preservation Principles

This implementation plan establishes a four-tier test gate architecture designed to reconcile the findings of the External Dependency Audit with rigorous release verification.

### Core Quality Preservation Principles:
1. **Never Remove Mandatory Tests:** Reclassifying an external engine as "optional" or "replaceable" does not lower the bar for the capability itself. ReBAC authorization, secret vaulting, durable DAG orchestration, real-time metering, and sandbox security remain non-negotiable.
2. **Acceptance by Contract, Not by Vendor:** Acceptance gates evaluate conformance to formal abstract domain contracts (`BaseAuthorizationEngine`, `BaseSecretVault`, etc.) rather than hard-coding dependencies to specific external server daemons.
3. **No Mocks for Live Gates:** Live integration gates require actual process restart, volume durability, or network boundary verification. Mocks or simulations remain clearly identified and cannot satisfy live tier requirements.
4. **Zero Weakening Before Replacement:** Authoritative release gates (`docs/CRITICAL_RELEASE_GATE_REPORT.md`) will not be replaced until the replacement test suites exist, execute, and receive formal sign-off.

---

## 2. Four-Tier Test Gate Taxonomy

```
+---------------------------------------------------------------------------------------------------------+
| CENTRAL INTELLIGENCE V1 — FOUR-TIER TEST ARCHITECTURE                                                   |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  TIER 1: Mandatory Functional Capabilities (Engine-Agnostic)                                            |
|  - Scope: ReBAC authorization, cryptographic vaulting, workflow execution, vector search, persistence.  |
|  - Runner: Local developer hosts, PR CI pipelines.                                                     |
|  - Enforcement: 100% Pass Required on all PRs and Releases. Zero skips.                                 |
|                                                                                                         |
|  TIER 2: Mandatory Security & Operations (Runtime Boundaries)                                          |
|  - Scope: Container sandbox isolation (12 controls), process crash recovery, volume durability,          |
|    fail-closed production guards, tamper-evident Merkle audit ledgers.                                 |
|  - Runner: Docker-enabled CI runners, standard staging hosts.                                          |
|  - Enforcement: 100% Pass Required for Release Candidate (RC1) and GA.                                  |
|                                                                                                         |
|  TIER 3: Optional Provider Compatibility (Distributed Enterprise Engines)                               |
|  - Scope: OpenFGA daemon, Infisical Node.js API, Lago Rails API, OpenMeter Kafka/CH, SigNoz APM cluster. |
|  - Runner: Dedicated 16 GB staging runner (e.g., GitHub Codespace / AWS Staging).                       |
|  - Enforcement: Required only when the specific provider is enabled in deployment configuration.       |
|                                                                                                         |
|  TIER 4: Deployment-Method-Specific Validation (Tooling & Infrastructure)                              |
|  - Scope: Kamal CLI deployment ordering, Bytebase DDL rollout, Docker Compose profile validation.       |
|  - Runner: Deployment CI runners / target deployment servers.                                           |
|  - Enforcement: Required prior to production infrastructure deployment.                                 |
|                                                                                                         |
+---------------------------------------------------------------------------------------------------------+
```

---

## 3. Exhaustive Test Gate Matrix

### Tier 1 — Mandatory Functional Capabilities (100% PR / Release Gate)

| Gate ID | Capability Domain | Concrete Acceptance Test | Test Command | Passing Criteria | Fallback Engine Evaluated |
|---|---|---|---|---|---|
| **G-T1.1** | ReBAC Authorization | `test_contract_authz_equivalence.py` | `pytest tests/unit/contracts/test_contract_authz_equivalence.py` | Transitive hierarchy resolution (`user -> group -> workspace -> document`), permission checks, cycle rejection. | Native SQLite/PostgreSQL Zanzibar CTE |
| **G-T1.2** | Secret Vaulting | `test_contract_secrets_equivalence.py` | `pytest tests/unit/contracts/test_contract_secrets_equivalence.py` | Authenticated AES-256-GCM encryption, zero-plaintext storage, key versioning, immutable audit entry creation. | Native SQLite Envelope Vault |
| **G-T1.3** | Durable Orchestration | `test_contract_workflow_equivalence.py` | `pytest tests/unit/contracts/test_contract_workflow_equivalence.py` | 5-node DAG execution, intermediate step checkpointing, resumption after simulated process kill. | Native SQLite WAL Orchestrator |
| **G-T1.4** | Relational Persistence | `test_fact_store_persists_and_recovers_across_restart` | `pytest tests/unit/test_ws04_durable_memory.py -k test_fact_store_persists` | ACID transactions, row-level locking (`FOR UPDATE`), schema creation, and restart recovery. | PostgreSQL / SQLite WAL |
| **G-T1.5** | Semantic Vector Search | `test_qdrant_vector_store_persists_on_disk` | `pytest tests/unit/test_ws04_durable_memory.py -k test_qdrant_vector` | Embedding persistence, HNSW indexing, cosine similarity threshold (`distance < 0.05`), payload filtering. | Qdrant `:memory:` / pgvector |
| **G-T1.6** | Token Accounting & Quota | `test_openmeter_cloudevent_schema_and_query` | `pytest tests/unit/test_ws05_billing_licensing.py -k test_openmeter` | CloudEvents 1.0 JSON validation, prompt/completion token accumulation, quota deduction accuracy. | Native PostgreSQL Token Ledger |
| **G-T1.7** | Reasoning Gateway Core | `test_gateway_core_routing` | `npm test` (@central-intelligence/reasoning) | Dynamic prompt routing, model hot-swap failover, session affinity, budget cap enforcement (317 tests). | Native TypeScript Gateway |

---

### Tier 2 — Mandatory Security & Operational Acceptance (100% Release Blocker)

| Gate ID | Security / Operational Requirement | Concrete Acceptance Test | Test Command | Passing Criteria | Security Controls Enforced |
|---|---|---|---|---|---|
| **G-T2.1** | Container Sandbox Isolation | `test_c3_sandbox_isolation_live.py` | `pytest tests/integration/test_c3_sandbox_isolation_live.py -m live` | All 12 runtime controls pass live: Linux container execution, zero capabilities (`CapEff=0`), read-only rootfs, blocked host mounts. | Drops all capabilities; blocks 45 host escape vectors |
| **G-T2.2** | Real Untrusted Python Execution | `test_sandbox_executes_real_python` | `pytest tests/integration/test_compose_stack_e2e.py -k test_sandbox_executes_real_python` | Ephemeral container executes `python3 -c 'print(2+2)'`, returns stdout `4`, zero simulation strings. | Memory capped at 128 MiB, CPU 1.0 |
| **G-T2.3** | Fail-Closed Production Guard | `test_production_guard_fail_closed` | `pytest tests/unit/test_production_guard.py` | When `ENVIRONMENT=production`, any unconfigured or unreachable live adapter raises `ProductionSafetyError`. | Zero mock leakage into production |
| **G-T2.4** | Multi-Tenant Data Segregation | `test_multi_tenant_isolation` | `pytest tests/unit/test_ws02_identity_governance.py` | Tenant A cannot read Tenant B's relational facts, vector embeddings, or secrets. 14/14 tests pass. | PostgreSQL RLS + tenant filtering |
| **G-T2.5** | Volume Durability Across Container Restart | `test_supabase_relational_and_vector_persist` | `pytest tests/integration/test_compose_stack_e2e.py -k test_supabase_relational` | Relational rows and vector embeddings survive hard `docker restart central-supabase-db`. | Named Docker volume durability |
| **G-T2.6** | Merkle Audit Chain Integrity | `test_tamper_evident_audit_ledger` | `pytest tests/unit/test_ws02_identity_governance.py -k test_merkle` | Sequential cryptographic hash chain detects any retroactive record modification or truncation. | SHA-256 Merkle root verification |

---

### Tier 3 — Optional Provider Compatibility (Environment-Gated)

| Gate ID | Provider | Compatibility Test | Environment Required | Current Verification Status | Reason Provider Is Optional |
|---|---|---|---|:---:|---|
| **G-T3.1** | **OpenFGA** | `test_openfga_persists_across_python_restart` | Standard Staging (OpenFGA + PG) | ✅ **PASS (Verified Live)** | Enterprise Zanzibar daemon; replaceable with SQLite ReBAC. |
| **G-T3.2** | **Infisical** | `test_infisical_persists_across_python_restart` | Standard Staging (Infisical + Valkey) | ✅ **PASS (Verified Live)** | Enterprise secrets vault; replaceable with embedded AES vault. |
| **G-T3.3** | **Temporal** | `test_temporal_workflow_survives_worker_restart` | Standard Staging (Temporal Server) | ✅ **PASS (Verified Live)** | Distributed orchestrator; replaceable with SQLite checkpoints. |
| **G-T3.4** | **Qdrant** | `test_qdrant_vector_store_persists_on_disk` | Standard Staging (Qdrant Daemon) | ✅ **PASS (Verified Live)** | Standalone vector DB; replaceable with pgvector or in-memory. |
| **G-T3.5** | **Apache AGE** | `test_age_graph_query_execution` | Standard Staging (Postgres 16 + AGE) | ✅ **PASS (Verified Live)** | OpenCypher graph engine; replaceable with NetworkX in-memory. |
| **G-T3.6** | **Lago** | `test_lago_persists_across_python_restart` | 16 GB Staging (Lago + Sidekiq + Redis) | 🟡 **BLOCKED (Requires 16 GB)** | Commercial billing engine; core AI operates without billing. |
| **G-T3.7** | **OpenMeter** | `test_openmeter_persists_across_python_restart` | 16 GB Staging (OpenMeter + Kafka + CH) | 🟡 **BLOCKED (Requires 16 GB)** | High-throughput streaming meter; replaceable with Postgres. |
| **G-T3.8** | **SigNoz** | `test_signoz_persists_across_python_restart` | 16 GB Staging (SigNoz ClickHouse Cluster)| 🟡 **BLOCKED (Requires 16 GB)** | Observability UI; adapter targets standard OTel endpoint. |
| **G-T3.9** | **LibreChat** | `test_librechat_routes_to_reasoning_gateway` | 16 GB Staging (LibreChat + Mongo) | 🟡 **BLOCKED (Requires 16 GB)** | Presentation chat UI; gateway works via API/CLI/Desktop. |

---

### Tier 4 — Deployment-Specific Validation

| Gate ID | Deployment Method | Validation Test | Execution Context | Current Status | Acceptance Criteria |
|---|---|---|---|:---:|---|
| **G-T4.1** | Docker Compose | `test_compose_profile_configuration` | `docker compose --profile standard config` | ✅ **PASS** | Valid syntax, all required secrets templated, zero resource conflicts. |
| **G-T4.2** | Bytebase DDL Rollout | `test_bytebase_migration_executes_real_ddl` | Standard Staging (`central-bytebase:5678`) | ✅ **PASS (Verified Live)** | Authenticated JWT, Sheet/Plan creation, Issue rollout to PostgreSQL. |
| **G-T4.3** | Automated Rollback Guard | `test_rollback_guard_reversibility` | Local / CI | ✅ **PASS** | Forward DDL migration and automated rollback verified without data loss. |
| **G-T4.4** | Kamal Rolling Deploy | `test_kamal_deployment_command_sequence` | CI Pipeline / Staging Server | 🟡 **SIMULATED (Pass)** | Command ordering verified: lock -> push -> boot -> proxy -> stop -> unlock. |

---

## 4. Pytest Test Categorization & CI Pipeline Integration

To enforce these tiers automatically, tests are decorated with explicit pytest markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "tier1_functional: Mandatory engine-agnostic functional capability acceptance tests",
    "tier2_security: Mandatory runtime security and operational durability acceptance tests",
    "tier3_provider: Optional third-party provider wire-compatibility tests",
    "tier4_deployment: Deployment-method and infrastructure lifecycle tests",
    "live: Requires live Docker containers or running network daemons",
    "requires_provisioned_services: Requires specific external services (Lago, OpenMeter, etc.)"
]
```

### GitHub Actions CI Workflow Structure

```yaml
# .github/workflows/ci.yml
name: Central Intelligence CI / Release Gates

jobs:
  pr_functional_and_security:
    name: "Tier 1 & Tier 2: Mandatory Gates (All PRs)"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python & Node
        uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Run TypeScript Tests
        run: npm test
      - name: Run Tier 1 Functional Tests
        run: pytest -m "tier1_functional"
      - name: Run Tier 2 Security & Sandbox Tests
        run: pytest -m "tier2_security"

  nightly_enterprise_staging:
    name: "Tier 3 & Tier 4: Enterprise Provider Gates (16 GB Runner)"
    runs-on: ubuntu-latest-8core-32gb  # Dedicated staging runner
    if: github.ref == 'refs/heads/main' || github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - name: Boot Enterprise Staging Stack
        run: docker compose --profile enterprise up -d
      - name: Run Tier 3 Optional Provider Compatibility
        run: pytest -m "tier3_provider"
      - name: Run Tier 4 Deployment Tooling Tests
        run: pytest -m "tier4_deployment"
```

---

## 5. Formal Gate Transition Protocol

The following step-by-step governance protocol governs the switch from historical gates to revised gates:

1. **Step 1 (Current): Approval of Revised Gate Architecture**
   - Present this specification to platform leads and stakeholders.
   - Maintain historical release gates in `docs/CRITICAL_RELEASE_GATE_REPORT.md` without modification.
2. **Step 2: Implementation of Equivalence Test Suites**
   - Author equivalence tests in `tests/unit/contracts/` for domains A through E.
   - Run tests against both embedded and external providers.
3. **Step 3: Verification on Clean Baseline**
   - Verify that 100% of Tier 1 and Tier 2 tests pass cleanly on both local developer machines and CI.
4. **Step 4: Formal Gate Sign-Off & Cutover**
   - Following successful Step 3 verification, update `docs/CRITICAL_RELEASE_GATE_REPORT.md` to authoritative status under the revised tier framework.
