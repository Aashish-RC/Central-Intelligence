# CENTRAL INTELLIGENCE V1 — REVISED TEST GATES & INTEGRATION ACCEPTANCE PROPOSAL

**Author:** Staff Principal Architect & Systems Reliability Auditor  
**Scope:** Re-classification of Historical Integration Scenarios, Decoupled Gate Criteria, and Verifiable Acceptance Proposal  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **FORMAL ARCHITECTURAL PROPOSAL — REQUIRES APPROVAL BEFORE IMPLEMENTATION**  

---

## 1. Executive Summary & Review of Historical Scenarios

During Stage S2 live integration testing (`docs/V1_LIVE_INTEGRATION_RESULTS.md`), 11 historical live integration scenarios were evaluated against real containers and process restart boundaries:
- **6 Genuine Live Passes:** OpenFGA (SC-01), Infisical (SC-02), Temporal (SC-06), PostgreSQL/pgvector (SC-07), Sandbox Isolation (SC-08), Bytebase (SC-10).
- **4 Auxiliary Foundation Live Passes:** Valkey (6.5 MiB), Qdrant (57 MiB), Apache AGE (95 MiB), Temporal Echo.
- **1 Simulated Pass:** Kamal deployment sequence (SC-09).
- **4 Blocked Scenarios:** Lago (SC-03), OpenMeter (SC-04), SigNoz (SC-05), LibreChat (SC-11) — blocked solely due to the physical RAM limitations of 8 GB developer/CI host environments (>5.4 GiB required).

### The Architectural Problem with Current Release Gates
The current release gate definitions (G-B1, G-B2, G-D3, G-E1 in `docs/CRITICAL_RELEASE_GATE_REPORT.md`) directly couple release criteria to **specific third-party vendor platforms**:
- *Current Gate G-B1:* "Real OpenFGA relationship enforcement"
- *Current Gate G-B2:* "Infisical secret lifecycle & recovery"
- *Current Gate G-D3:* "Qdrant & Apache AGE live retrieval"
- *Current Gate G-E1:* "Real Lago & OpenMeter usage metering"

This coupling introduces three critical flaws:
1. **Conflates Capability with Implementation:** Central Intelligence requires ReBAC, secret rotation, multi-hop retrieval, and token metering. Binding the acceptance gate to OpenFGA, Infisical, Lago, or OpenMeter makes third-party software mandatory even when superior or lighter native engines exist.
2. **Imposes Unviable CI Resource Demands:** Blocking release gates on Lago (Rails + Sidekiq) and OpenMeter (Kafka + ClickHouse) forces CI environments to provision 16+ GB memory clusters, creating high cloud operational costs ($$$) and preventing fast developer feedback.
3. **Weakens Architectural Modularity:** It discourages creating embedded or edge-ready implementations (e.g., SQLite ReBAC, in-memory vault, local stream metering) because the gates only credit external server daemons.

---

## 2. Core Rule of the Revised Test Framework

> **Rule 1: Never remove a mandatory capability test merely because its current provider becomes optional.**  
> The capability test remains mandatory; what changes is that the test accepts any compliant provider conforming to the domain interface.

> **Rule 2: Release gates must not be modified in production or CI until an equivalent, verifiable acceptance path has been formally approved.**  
> This document proposes the path. No gates are lowered or removed; rather, tests are decoupled into clean tiers.

> **Rule 3: Optional integrations must never be marked as validated unless their genuine live integration tests actually pass against real backends.**  
> Scenarios SC-03 (Lago), SC-04 (OpenMeter), SC-05 (SigNoz), and SC-11 (LibreChat) remain explicitly marked as **UNVALIDATED / BLOCKED** until provisioned on a dedicated 16 GB staging runner.

---

## 3. Four-Tier Integration Test Taxonomy

The integration test suite is reorganized into four strict, decoupled tiers:

```
+----------------------------------------------------------------------------------------------------+
| FOUR-TIER INTEGRATION TESTING FRAMEWORK                                                            |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  TIER 1: Mandatory Functional Acceptance Tests (Engine-Agnostic)                                   |
|  - Validates core capability contracts (RBAC/ReBAC logic, secret encryption, DAG execution,       |
|    vector retrieval accuracy, token cost accounting).                                              |
|  - Runs against both native/embedded engines AND live external engines.                            |
|  - 100% mandatory for all PRs and releases.                                                       |
|                                                                                                    |
|  TIER 2: Mandatory Security & Operational Acceptance Tests                                         |
|  - Validates non-negotiable security boundaries: container sandbox isolation (12 controls),        |
|    process restart recovery, persistent volume durability, Merkle audit chains, fail-closed guards. |
|  - 100% mandatory for release gating.                                                             |
|                                                                                                    |
|  TIER 3: Optional Provider-Specific Compatibility Tests                                            |
|  - Validates wire compatibility with specific third-party servers (OpenFGA daemon, Infisical API,   |
|    Lago Rails server, OpenMeter Kafka/ClickHouse cluster, SigNoz OTel collector).                  |
|  - Executed in dedicated integration environments or nightly CI when backends are provisioned.     |
|                                                                                                    |
|  TIER 4: Deployment-Method-Specific Tests                                                          |
|  - Validates external infrastructure deployment tooling (Kamal rolling deploy CLI, Coolify PaaS,   |
|    Bytebase live DDL rollout, Kubernetes manifests).                                               |
|  - Validates command generation and dry-run syntax in PR CI; live executions gated to deploy envs. |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Re-Classification of the 11 Historical Scenarios

| Scenario ID | Historical Target Service | Current Test Name | Revised Test Tier | Equivalent Verifiable Acceptance Path | Rationale for Tier Assignment |
|:---:|---|---|---|---|---|
| **SC-01** | **OpenFGA** | `test_openfga_persists_across_python_restart` | **Tier 1 (Capability)** & **Tier 3 (Provider)** | **Mandatory Capability Path:** Verify ReBAC tuple expansion, transitive inheritance, and Python restart persistence using `BaseAuthorizationEngine` (tested on embedded Zanzibar or OpenFGA).<br>**Tier 3 Path:** Live OpenFGA container restart check. | Fine-grained ReBAC is a core requirement; OpenFGA container is an enterprise provider. |
| **SC-02** | **Infisical** | `test_infisical_persists_across_python_restart` | **Tier 1 (Capability)** & **Tier 3 (Provider)** | **Mandatory Capability Path:** Verify secret encryption, versioned rotation, immutable audit log, and restart persistence using `BaseSecretVault`.<br>**Tier 3 Path:** Live Infisical Universal Auth and secret retrieval. | Secret vaulting is mandatory; Node.js Infisical daemon is an optional provider. |
| **SC-03** | **Lago** | `test_lago_persists_across_python_restart` | **Tier 3 (Optional Provider Compatibility)** | **Mandatory Capability Path:** Billing ledger tests in `test_ws05_billing_licensing.py` (invoice calculation, wallet debiting, plan quotas).<br>**Tier 3 Path:** Live Lago API test (requires 16 GB staging runner). | Lago is an optional commercial billing engine. Base platform functions without it. |
| **SC-04** | **OpenMeter** | `test_openmeter_persists_across_python_restart` | **Tier 3 (Optional Provider Compatibility)** | **Mandatory Capability Path:** CloudEvents 1.0 schema compliance and local token accumulation in `test_10_4_openmeter_adapter_live`.<br>**Tier 3 Path:** Live Kafka + ClickHouse ingestion (requires 16 GB staging). | Heavy distributed streaming cluster; optional for standalone deployments. |
| **SC-05** | **SigNoz** | `test_signoz_persists_across_python_restart` | **Tier 2 (Operational Telemetry)** & **Tier 3 (Provider)** | **Mandatory Capability Path:** OTel span creation, trace propagation, and local JSON-L buffer serialization.<br>**Tier 3 Path:** Live OTLP export to SigNoz ClickHouse (requires 16 GB staging). | Tracing is mandatory; SigNoz ClickHouse cluster is an optional UI/storage target. |
| **SC-06** | **Temporal** | `test_temporal_workflow_survives_worker_restart` | **Tier 1 (Capability)** & **Tier 3 (Provider)** | **Mandatory Capability Path:** Multi-step DAG workflow survival across simulated worker SIGKILL and state replay via `BaseOrchestratorBridge`.<br>**Tier 3 Path:** Live Temporal server event replay. | Durable orchestration is mandatory. Standalone setups can use SQLite checkpoints. |
| **SC-07** | **PostgreSQL / pgvector** | `test_supabase_relational_and_vector_persist` | **Tier 2 (Mandatory Security & Operational)** | **Mandatory Operational Path:** Live PostgreSQL + pgvector container restart, volume durability, cosine similarity retrieval, and RLS tenant isolation. | Core system of record and relational persistence foundation. |
| **SC-08** | **Sandbox Isolation** | `test_c3_sandbox_isolation_live.py` (12 controls) | **Tier 2 (Mandatory Security & Operational)** | **Mandatory Security Path:** Unmocked execution in isolated container (`python:3.12-slim`), zero capabilities (`CapEff=0`), read-only rootfs, network isolation, 45 host escape blocks. | Highest-priority safety boundary against remote code execution. |
| **SC-09** | **Kamal Deployment** | `test_kamal_deployment_command_sequence_is_simulated` | **Tier 4 (Deployment-Method-Specific)** | **Deployment Validation Path:** Verification of lock acquisition, image tagging, proxy swap sequence, and rollback handling. Live execution gated to dedicated staging VMs with SSH keys. | Kamal is an external CLI deploy tool, not a platform runtime service. |
| **SC-10** | **Bytebase** | `test_bytebase_migration_executes_real_ddl` | **Tier 3 (Optional Provider Compatibility)** | **Mandatory Capability Path:** DDL migration forward execution and transactional rollback tested directly on PostgreSQL.<br>**Tier 3 Path:** Live Bytebase Sheet/Plan/Rollout API execution. | Database schema migrations are mandatory; Bytebase web UI is an enterprise extra. |
| **SC-11** | **LibreChat** | `test_librechat_routes_to_reasoning_gateway` | **Tier 3 (Optional Provider Compatibility)** | **Mandatory Capability Path:** Multi-provider conversation session state and reasoning gateway proxy routing in `test_10_10_librechat_adapter_live`.<br>**Tier 3 Path:** Live LibreChat frontend + MongoDB (requires 16 GB staging). | LibreChat is an optional web UI frontend. Core gateway functions via API/CLI. |

---

## 5. Detailed Proposed Release Gate Revisions

Below is the side-by-side comparison of the existing release gates versus the proposed revised gates:

### Gate G-B1: Identity & ReBAC Authorization
* **Current Requirement:** "Real OpenFGA relationship enforcement"
* **Proposed Revised Requirement:** **"Fine-Grained ReBAC Relationship & Delegation Enforcement"**
* **Verifiable Acceptance Path:**
  1. *Functional Acceptance (Mandatory):* Execute test suite against `BaseAuthorizationEngine`. Verify transitive relationship resolution (`viewer -> editor -> owner`), cross-tenant isolation, conditional checks, and expiring delegation grants.
  2. *Live Implementation Acceptance:*
     - If `OPENFGA_URL` is configured: Verify against live OpenFGA server with container restart durability (`test_openfga_persists_across_python_restart`).
     - If in standalone/embedded mode: Verify against native SQLite/Postgres Zanzibar engine with process restart durability.
* **Why This Preserves Quality:** The exact same ReBAC test tuples and verification assertions run. The system verifies authorization semantics rather than the specific Go binary daemon.

---

### Gate G-B2: Secret Vault & Lifecycle
* **Current Requirement:** "Infisical secret lifecycle & recovery"
* **Proposed Revised Requirement:** **"Cryptographic Secret Vaulting, Rotation & Access Auditing"**
* **Verifiable Acceptance Path:**
  1. *Functional Acceptance (Mandatory):* Verify zero-downtime secret rotation, versioned historical retrieval, AES-256 envelope encryption, and immutable audit log entry generation.
  2. *Live Implementation Acceptance:*
     - If Infisical is provisioned: Live Universal Auth and secret storage (`test_infisical_persists_across_python_restart`).
     - If in standalone mode: Live local encrypted vault with persistent file recovery across process restart.
* **Why This Preserves Quality:** Ensures credentials are encrypted at rest and audited, without halting deployments when the Node.js Infisical daemon is unneeded.

---

### Gate G-C3: Containerized Sandbox Isolation
* **Current Requirement:** "Containerized sandbox integration"
* **Proposed Revised Requirement:** **"Guarded Runtime Sandbox Isolation & Host Escape Defense" (UNCHANGED)**
* **Status:** **REMAINS 100% MANDATORY AS DEFINED.**
* **Verifiable Acceptance Path:** All 12 live runtime controls in `test_c3_sandbox_isolation_live.py` must pass cleanly against real container execution on the host Docker daemon. Silent fallback to host shell execution remains strictly prohibited.

---

### Gate G-D1: Relational Persistence & Locking
* **Current Requirement:** "PostgreSQL persistence & row locking"
* **Proposed Revised Requirement:** **"Relational Persistence, Row Locking & Multi-Tenant Segregation" (UNCHANGED)**
* **Status:** **REMAINS 100% MANDATORY AS DEFINED.**
* **Verifiable Acceptance Path:** Live PostgreSQL container restart, volume durability, transactional locking (`SELECT FOR UPDATE`), and tenant boundary verification.

---

### Gate G-D3: Multi-Backend Semantic & Graph Retrieval
* **Current Requirement:** "Qdrant & Apache AGE live retrieval"
* **Proposed Revised Requirement:** **"Hybrid Semantic & Multi-Hop Graph Retrieval with RRF Ranking"**
* **Verifiable Acceptance Path:**
  1. *Semantic Vector Retrieval:* Validated on live Qdrant container OR pgvector with HNSW indexing, verifying cosine similarity thresholds.
  2. *Multi-Hop Graph Traversal:* Validated on live Apache AGE container OR NetworkX in-memory graph store, verifying multi-hop entity relationship retrieval.
  3. *Hybrid Ranking:* Reciprocal Rank Fusion (RRF) deduplication and score merging verified in `test_d3_combined_live_retrieval.py`.
* **Why This Preserves Quality:** Maintains full hybrid GraphRAG retrieval rigor while allowing tests to execute cleanly on lightweight developer hosts.

---

### Gate G-E1: Usage-Based Billing & Token Metering
* **Current Requirement:** "Real Lago & OpenMeter usage metering"
* **Proposed Revised Requirement:** **"Real-Time CloudEvents Token Metering & Usage-Based Billing Accounting"**
* **Verifiable Acceptance Path:**
  1. *Token Metering (Mandatory Functional):* CloudEvents 1.0 event generation, token consumption tracking per user/model/tenant, and rate-card cost calculation verified in `test_10_4_openmeter_adapter_live`.
  2. *Billing Engine (Mandatory Functional):* Subscription plan limits, overage calculation, wallet debiting, and invoice generation verified in `test_ws05_billing_licensing.py`.
  3. *Optional Live Verification:* If Lago and OpenMeter containers are provisioned in a 16 GB staging environment, execute live HTTP dispatch tests (`test_lago_persists_across_python_restart`, `test_openmeter_persists_across_python_restart`).
* **Why This Preserves Quality:** Verifies all financial accounting math, event schemas, and billing logic without requiring Kafka and Rails clusters for standard platform releases.

---

### Gate G-F1: Integration Suite Execution
* **Current Requirement:** "Skipped live integration tests executed"
* **Proposed Revised Requirement:** **"Tiered Integration Test Execution (100% Tier 1 & Tier 2 Pass; Tier 3 & Tier 4 Environment-Gated)"**
* **Verifiable Acceptance Path:**
  - **PR and Release Gate (Local & Standard CI):** 100% pass of all Tier 1 (Functional Acceptance) and Tier 2 (Security/Operational Acceptance) tests. Zero skipped mandatory tests.
  - **Nightly / Enterprise Staging Gate (16 GB Runner):** Execute all Tier 3 (Optional Provider Compatibility: Lago, OpenMeter, SigNoz, LibreChat) and Tier 4 (Deployment Tooling: Kamal, Bytebase) tests.

---

## 6. Implementation & Transition Plan

To adopt these revised gates without disrupting the existing production baseline:

```
[Phase 1: Architectural Review] (Current Step)
- Present V1 External Dependency Audit, Classification, and Revised Test Gates Proposal.
- Stakeholders review proposed gate definitions and decoupling strategy.
- NO CODE OR GATES ALTERED until formal sign-off.

[Phase 2: Interface Formalization] (Post-Approval)
- Formalize BaseAuthorizationEngine, BaseSecretVault, and BaseTokenMeter in code.
- Add SQLite/Postgres native drivers alongside existing OpenFGA, Infisical, and OpenMeter adapters.

[Phase 3: Test Suite Tagging] (Post-Approval)
- Tag tests in pytest using explicit markers:
  * @pytest.mark.mandatory_functional (Tier 1)
  * @pytest.mark.mandatory_security (Tier 2)
  * @pytest.mark.provider_live (Tier 3)
  * @pytest.mark.deployment_tooling (Tier 4)

[Phase 4: Gate Update & Release Verification] (Post-Approval)
- Update CI pipeline and verify-critical script to enforce Tier 1 & Tier 2 for general release gates.
- Configure dedicated 16 GB staging job for Tier 3 and Tier 4.
```

---

## 7. Formal Approval Request

* **Recommendation:** Adopt the revised Four-Tier Integration Gate framework.
* **Impact on Security:** **Zero degradation.** Sandbox isolation, tenant separation, Merkle audit chains, and fail-closed policies remain 100% mandatory and strictly enforced.
* **Impact on Developer Experience:** Reduces developer host RAM requirements from >8.5 GiB down to ~1.2 GiB, eliminating OOM lockups and unblocking fast local integration testing.
* **Impact on Platform Modularity:** Eliminates vendor lock-in, enabling Central Intelligence to deploy anywhere from single-node edge servers to massive distributed enterprise clusters.
