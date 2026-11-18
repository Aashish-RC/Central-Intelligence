# Central Intelligence — V1 Blockers, Residual Risks & Mitigation Register

**Author:** Principal Security Reviewer, Infrastructure Architect & QA Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `75b2666a4bc2cbb242637b830d1ff69e88b6932a` (`75b2666`)  
**Date:** 2026-11-19  
**Status:** **AUTHORITATIVE RISK & BLOCKER REGISTER (RECONCILED RELEASE BASELINE)**  

---

## 1. Active Release Blockers

The following items are the tracked blockers and operational gates for Release Candidate 1 (RC1) and GA Production Release:

| Blocker ID | Category | Description | Impact | Current Status | Required Action / Owner |
|---|---|---|---|---|---|
| **BLK-01** | Live Integration | Multi-tier enterprise integration: SigNoz (SC-05) full cluster OTel/ClickHouse/ZooKeeper. | Telemetry trace ingestion and query verification against real ClickHouse. | **RESOLVED** | Executed in local environment with standalone ingester and ClickHouse 25.12; 48.02s live pass recorded without host memory exhaustion. (Commit `0aaed35`) |
| **BLK-02** | Hardware / Memory | Local PC (8 GB RAM, 3.72 GiB WSL2 Docker ceiling) cannot safely start the full 51-service stack simultaneously. | Concurrent startup triggers OOM killer across ClickHouse, Kafka, and telemetry clusters. | **RESOLVED by Operational Profiles** | Adopted Lite (~315 MiB), Standard (~910 MiB), and Enterprise (~4.8 GiB) profiles; maintained 8 running containers under 1.2 GiB on developer hosts. (Owner: Infra Lead) |
| **BLK-03** | Database Protection | Target database volume durability and disposable schema isolation required live verification. | Potential state corruption if tests touch stateful shared databases. | **RESOLVED** | Verified named volume `central-intelligence_supabase_data`, multi-database isolation (`openfga`, `infisical`, `lago`, `openmeter`, `signoz`), and isolated schema drop patterns. (Owner: Data Lead) |
| **BLK-04** | Sandbox Execution | Unmocked container execution required live daemon activation with strict isolation. | Ensuring agent runtime code cannot escape or escalate privileges on host. | **RESOLVED** | Verified 12/12 C3 runtime isolation controls and live container stdout execution (`print(2+2)` -> `4`). (Owner: Security Lead) |
| **BLK-05** | Surface Chat Flow | LibreChat custom endpoint configuration is mounted, but live authenticated UI-originated chat traversing to reasoning gateway required browser proof. | End-to-end user journey requires verification of browser session to model output. | **RESOLVED** | Verified via Playwright headless Chrome: authenticated session -> LibreChat UI -> Custom Endpoint "Central Intelligence" (GPT-4o) -> Layer 4 Reasoning Gateway (:4000) -> assistant response rendered in DOM and verified in 14.67s (`tests/integration/test_librechat_e2e.py`). (Commit `ff483a4`) |
| **BLK-06** | Test Gate Decoupling | Historical release gates G-B1, G-B2, G-D3, G-E1 hard-code vendor server daemons. | Blocks release sign-off when native or embedded engines are utilized. | **PROPOSED & SPECIFIED** | Formal proposal in `docs/V1_REVISED_TEST_GATES_PROPOSAL.md` and implementation plan in `docs/V1_REVISED_TEST_GATE_IMPLEMENTATION_PLAN.md`; awaiting administrative sign-off before modifying authoritative gates. (Owner: QA Lead) |
| **BLK-07** | Operational Reliability | Uninterrupted 24-hour continuous soak execution. | Proves zero memory leaks, thread starvation, or handle exhaustion over prolonged operation. | **HARNESS READY / EXECUTION PENDING** | Bounded-memory soak test passed (31.4s) and 24h staging daemon implemented (`scripts/soak_runner_24h.py`); requires dedicated persistent CI/staging runner to execute 24h uninterrupted run. (Owner: Reliability Lead) |
| **BLK-08** | Security Assurance | Formal independent third-party penetration audit and executive security sign-off. | Regulatory, compliance, and multi-tenant security verification. | **TECHNICAL PASS / AUDIT PENDING** | Automated red-team suite (96/96 blocked, 100% detection rate) and 226 safety tests passed cleanly; formal external penetration test report and CISO sign-off required prior to production release. (Owner: Security Lead) |
| **BLK-09** | Deployment Verification | Clean-host OS bootstrap drill on fresh VM. | Proves zero-dependency fresh environment initialization. | **HARNESS VERIFIED / STAGING DRILL PENDING** | Cross-platform bootstrap scripts and `.env` generator passed 7/7 automated tests; drill on clean Ubuntu/Debian VM required in staging. (Owner: DevOps Lead) |
| **BLK-10** | Release Governance | Formal production release authorization. | Ensures no production release occurs without documented executive stakeholder approval. | **PENDING** | Formal approval required from Product Owner, Principal Architect, and Security Lead prior to executing S6 production deployment. (Owner: Release Manager) |

---

## 2. Residual Technical & Operational Risks

| Risk ID | Risk Title | Severity | Likelihood | Impact Description | Mitigation Strategy | Owner |
|---|---|:---:|:---:|---|---|---|
| **RSK-01** | Multi-Tenant Database Cross-Talk | High | Low | If PostgreSQL databases are consolidated into a single instance, a configuration error in role permissions could allow tenant cross-talk. | Strict role-based database separation: each service/tenant connects with unique non-superuser role restricted to its own database schema. Unit test suite `test_ws02` validates cross-tenant isolation. | Data & Security Teams |
| **RSK-02** | Lago AGPL-3.0 Licensing Boundary | High | Low | Accidental static linking or in-process importing of Lago libraries could compromise Central Intelligence's Apache-2.0 licensing. | Enforce architectural quarantine: Lago runs in an isolated container on `agpl_quarantine_net`; Python codebase interacts strictly via external HTTP REST APIs (`LAGO_IMPORT_RE` verified in `scripts/check_licenses.py`). | Legal & Release Coordinator |
| **RSK-03** | Non-OSI Dependency Contagion (RSALv2 / SSPL) | Medium | Low | Upstream Redis 7.4+ and MongoDB 7.0 carry RSALv2 / SSPL-v1 licenses which are non-OSI. | Valkey (BSD-3-Clause) adopted as primary cache, replacing Redis containers. MongoDB moved to optional `--profile ui`, keeping core runtime 100% OSI-approved. | License Compliance Officer |
| **RSK-04** | Memory Contention Under Sustained Load | Medium | Medium | In Standard profile, multiple services running simultaneously near the memory limit could cause transient page swapping. | Enforce strict `deploy.resources.limits.memory` on all Compose services; configure swap ceilings in `.wslconfig`; enable capability-driven dynamic idle shutdown. | Infrastructure Lead |
| **RSK-05** | SigNoz Ingester AMD64 Digest on ARM64 | Low | Medium | SigNoz ingester is pinned to an AMD64 container digest, causing emulation slowdowns on Apple Silicon / ARM64 developer machines. | Maintain multi-arch manifest digests in Compose configuration. | Release Coordinator |
| **RSK-06** | Temporal Workflow Determinism Drift | High | Low | Changes to agent workflow code could break determinism for in-flight workflows upon deployment. | Enforce Temporal workflow versioning (`workflow.patched`) and deterministic replay test suite before upgrading worker code. | Orchestration Team |
| **RSK-07** | Kamal External Deployment Credential Exposure | High | Low | Automated CI deployments with Kamal require root SSH keys and container registry tokens. | Restrict Kamal execution to dedicated staging CI runners with ephemeral credentials; do not store production SSH keys in local `.env`. | DevOps Lead |

---

## 3. Contingency & Fallback Plans

1. **If Staging Environment Resources are Constrained:** Fall back to staged sequential container startup on local PC: run Batch 1 (Data), verify and teardown; run Batch 2 (Identity), verify and teardown. Never run all rings concurrently on 8 GB host.
2. **If External Reasoning Providers Fail or Exceed Rate Limits:** The Model Hot-Swap Manager (`platform_infra/compute/lifecycle/hot_swap.py`) automatically fails over to secondary and tertiary providers in the configured fallback chain with zero request drops.
3. **If OpenMeter / Lago Billing Infrastructure is Offline:** The billing governor fails closed for unmetered billable requests while allowing BYOK (Bring Your Own Key) requests to proceed without disruption.
4. **If Qdrant Vector Database is Unavailable:** Cognitive retrieval falls back to pgvector inside PostgreSQL, and subsequently to SQLite local semantic cache.
5. **If External OpenFGA or Infisical Daemons are Offline:** In Lite deployment profile, the system activates the embedded SQLite/PostgreSQL Zanzibar engine and native AES-256-GCM envelope vault, ensuring continuous zero-dependency operation.
