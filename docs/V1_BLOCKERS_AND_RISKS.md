# Central Intelligence — V1 Blockers, Residual Risks & Mitigation Register

**Author:** Principal Security Reviewer, Infrastructure Architect & QA Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `af93f635fe225be0023b851bab982a52fa69b67c` (`af93f63`)  
**Date:** 2026-11-18  
**Status:** **ACTIVE RISK & BLOCKER REGISTER (STAGE S2 INTEGRATION RECOVERY)**

---

## 1. Active Release Blockers

The following items are active blockers preventing unconditional sign-off for Release Candidate 1 (RC1) and GA Production Release:

| Blocker ID | Category | Description | Impact | Current Status | Required Action / Owner |
|---|---|---|---|---|---|
| **BLK-01** | Live Integration | Remaining multi-tier enterprise integrations (Lago, OpenMeter, SigNoz, LibreChat) exceed 8 GB host memory headroom. | Prevents simultaneous execution on 8 GB laptop without OOM thrashing. | **BLOCKED (Requires 16 GB Staging)** | Execute in approved 16 GB disposable staging environment (e.g. GitHub Codespace). Infisical (SC-02) and Bytebase (SC-10) are fully unblocked and verified live. (Owner: DevOps / QA Lead) |
| **BLK-02** | Hardware / Memory | Local PC (8 GB RAM, 3.72 GiB WSL2 Docker ceiling) cannot safely start the full 37-service enterprise profile simultaneously. | Concurrent startup triggers OOM killer across ClickHouse, Kafka, and telemetry clusters. | **MITIGATED by M1 Profiles** | Enforce sequential execution; maintain 8 running containers under 1.2 GiB; execute full 37-service enterprise validation in 16 GB staging. (Owner: Infra Lead) |
| **BLK-03** | Database Protection | Target database volume durability and disposable schema isolation required live verification. | Potential state corruption if tests touch stateful shared databases. | **RESOLVED** | Verified named volume `central-intelligence_supabase_data`, multi-database isolation (`openfga`, `infisical`, `lago`, `openmeter`, `signoz`), and isolated schema drop patterns. (Owner: Data Lead) |
| **BLK-04** | Sandbox Execution | Unmocked container execution required live daemon activation with strict isolation. | Ensuring agent runtime code cannot escape or escalate privileges on host. | **RESOLVED** | Verified 12/12 C3 runtime isolation controls and live container stdout execution (`print(2+2)` -> `4`). (Owner: Security Lead) |
| **BLK-05** | Surface Chat Flow | LibreChat custom endpoint configuration is mounted, but live authenticated UI-originated chat traversing to reasoning gateway is not demonstrated. | End-to-end user journey requires verification of browser session to model output. | **PENDING EXECUTION** | Run automated headless Playwright/Puppeteer script through LibreChat UI to gateway in 16 GB staging environment. (Owner: Surface Lead) |

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

---

## 3. Contingency & Fallback Plans

1. **If Codespaces resources are constrained:** Fall back to staged sequential container startup on local PC: run Batch 1 (Data), verify and teardown; run Batch 2 (Identity), verify and teardown. Never run all rings concurrently on 8 GB host.
2. **If external reasoning providers fail or exceed rate limits:** The Model Hot-Swap Manager (`platform_infra/compute/lifecycle/hot_swap.py`) automatically fails over to secondary and tertiary providers in the configured fallback chain with zero request drops.
3. **If OpenMeter / Lago billing infrastructure is offline:** The billing governor fails closed for unmetered billable requests while allowing BYOK (Bring Your Own Key) requests to proceed without disruption.
4. **If Qdrant vector database is unavailable:** Cognitive retrieval falls back to pgvector inside PostgreSQL, and subsequently to SQLite local semantic cache.
