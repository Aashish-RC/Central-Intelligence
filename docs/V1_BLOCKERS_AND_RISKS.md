# Central Intelligence — V1 Blockers, Residual Risks & Mitigation Register

**Author:** Principal Security Reviewer, Infrastructure Architect & QA Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `54ae6e7d23874676f3f7d7fb181242311d97da06`  
**Date:** 2026-11-17  
**Status:** **ACTIVE RISK & BLOCKER REGISTER**

---

## 1. Active Release Blockers

The following items are active blockers preventing unconditional sign-off for Release Candidate 1 (RC1) and GA Production Release:

| Blocker ID | Category | Description | Impact | Current Status | Required Action / Owner |
|---|---|---|---|---|---|
| **BLK-01** | Live Integration | Missing authenticated disposable test endpoints/credentials for Infisical, Lago, Bytebase, and Reasoning Gateway. | Prevents genuine live execution of scenarios 2, 3, 10, 11 in `test_compose_stack_e2e.py`. | **BLOCKED (Fail-Closed)** | Provide disposable integration credentials in GitHub Codespaces environment. (Owner: DevOps / QA Lead) |
| **BLK-02** | Hardware / Memory | Local PC (8 GB RAM, 3.72 GiB WSL2 Docker ceiling) cannot safely start the full 37-service legacy core profile simultaneously. | Concurrent startup triggers OOM killer (Exit Code 137) across Kafka, Keycloak, Supabase, and Temporal. | **MITIGATED by M1 Profiles** | Enforce `lite` and `standard` profiles; execute full 37-service enterprise validation in 16 GB Codespaces. (Owner: Infra Lead) |
| **BLK-03** | Database Protection | `POSTGRES_LIVE_URL` is set in local environment, but target database is not confirmed disposable. | Test suite cannot execute real DDL table creation and embedding mutation against user's potential production/stateful store. | **BLOCKED (Fail-Safe)** | Provision isolated disposable test database or execute against ephemeral Compose Postgres volume. (Owner: Data Lead) |
| **BLK-04** | Sandbox Execution | `SANDBOX_LIVE=1` test is unverified against live Docker daemon due to remote execution provider guard. | Sandbox isolation controls verified via in-repo test suite, but end-to-end unmocked container execution requires local daemon activation. | **PENDING EXECUTION** | Run unmocked test against local Docker container engine with strict cgroup limits. (Owner: Security Lead) |
| **BLK-05** | Surface Chat Flow | LibreChat custom endpoint configuration is mounted, but live authenticated UI-originated chat traversing to reasoning gateway is not demonstrated. | End-to-end user journey requires verification of browser session to model output. | **PENDING EXECUTION** | Run automated headless Playwright/Puppeteer script through LibreChat UI to gateway. (Owner: Surface Lead) |

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
