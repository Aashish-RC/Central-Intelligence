# CENTRAL INTELLIGENCE V1 — DEDICATED TEST EXECUTION PLAN

**Author:** Principal QA Lead, Security Architect & Release Coordinator  
**Target:** Central Intelligence v1 Testing & Operational Validation Phase (Stages S2, S3, S4)  
**Date:** 2026-11-17  
**Build Revision:** `54ae6e7d23874676f3f7d7fb181242311d97da06` (`54ae6e7`)  
**Status:** **ACTIVE TEST EXECUTION PLAN**  

---

## 1. Overview & Test Phase Objectives

Following the 100% build sign-off (`docs/V1_BUILD_SIGNOFF.md`), this document defines the execution strategy, staging environments, credential injection, sequential service groupings, acceptance criteria, and disaster drills required to validate Central Intelligence v1 for Release Candidate 1 (RC1) and Production GA.

**Operating Principles:**
- **Zero Production Mutation:** Testing is strictly isolated to disposable, ephemeral staging environments (GitHub Codespaces or isolated test runners).
- **Sequential Startup Safety:** The 37-service enterprise stack is partitioned into safe sequential startup groups to avoid host OOM crashes on constrained environments.
- **Fail-Closed Verification:** Every scenario must pass with authenticated live services; mocked or simulated passes must never be counted as genuine live integration passes.

---

## 2. Test Execution Environments & Credential Provisioning

### 2.1 Staging Environment Profiles

| Environment | Purpose | Hardware Allocation | Staged Stack |
|---|---|---|---|
| **Primary Testing Staging** | Full 11-service integration, 24h soak, chaos drills | **GitHub Codespaces (16 GB RAM, 4 vCPU, 32 GB SSD)** | Multi-profile Compose (`standard` / `enterprise`) |
| **Local CI / Verification** | Fast unit tests, packaging, linting, regression suites | **Local PC (8 GB RAM, 3.72 GiB WSL2 ceiling)** | `--profile lite` with Capability Activation Engine |
| **Quarantine Testing Net** | AGPL/non-OSI boundary testing (Lago, Infisical, OpenMeter) | **Isolated Docker Network (`agpl_quarantine_net`)** | Lago container + REST boundary tests |

### 2.2 Disposable Credential Injection Matrix

The following ephemeral environment variables are injected into the staging `.env.test.staging` file:

```bash
# Disposable Staging Credentials (Vault / CI Secrets)
OPENFGA_LIVE_URL="http://openfga:8080"
OPENFGA_STORE_ID="01HQTESTSTORE0000000000000"
OPENFGA_API_TOKEN="disposable_test_token_openfga"

INFISICAL_LIVE_URL="http://infisical:8080"
INFISICAL_CLIENT_ID="test_client_id_staging"
INFISICAL_CLIENT_SECRET="test_client_secret_staging"
INFISICAL_PROJECT_ID="test_project_uuid"

LAGO_LIVE_URL="http://lago-api:3000"
LAGO_API_KEY="test_lago_api_key_staging"

OPENMETER_LIVE_URL="http://openmeter:8888"
OPENMETER_TOKEN="test_openmeter_token_staging"

SIGNOZ_LIVE_URL="http://signoz-signoz-0:3301"
SIGNOZ_QUERY_TOKEN="test_signoz_query_token"

TEMPORAL_LIVE_URL="temporal:7233"
TEMPORAL_NAMESPACE="default"

BYTEBASE_LIVE_URL="http://bytebase:8080"
BYTEBASE_SERVICE_KEY="test_bytebase_key"

POSTGRES_DISPOSABLE_URL="postgresql://postgres:postgres@supabase-db:5432/test_disposable_db"
VALKEY_LIVE_URL="redis://valkey:6379/1"
QDRANT_LIVE_URL="http://qdrant:6333"

SANDBOX_LIVE=1
DOCKER_HOST="unix:///var/run/docker.sock"
```

---

## 3. Safe Sequential Service Startup Groups

To guarantee zero out-of-memory container terminations, services are brought online in 4 sequential rings:

```mermaid
flowchart LR
    G1["Group 1: Foundation\n(PostgreSQL, Valkey, Qdrant)"] --> G2["Group 2: Identity & Security\n(OpenFGA, Infisical)"]
    G2 --> G3["Group 3: Telemetry & Billing\n(OTel, SigNoz, OpenMeter, Lago)"]
    G3 --> G4["Group 4: Orchestration & Surface\n(Temporal, LibreChat, Gateway)"]
```

### Group 1: Core Foundation Ring (Ring 0)
- **Services:** `supabase-db` (Postgres + pgvector), `valkey` (caching), `qdrant` (vector store), `apache-age` (graph).
- **RAM Ceiling:** 960 MiB.
- **Health Check Command:**
  ```powershell
  docker compose --profile lite up -d supabase-db valkey qdrant
  docker compose exec supabase-db pg_isready -U postgres
  curl -s http://localhost:6333/healthz
  ```
- **Acceptance:** Ports 5432, 6379, 6333 listening and accepting read/write transactions.

### Group 2: Identity, Governance & Secrets Ring (Ring 1)
- **Services:** `openfga`, `infisical`.
- **RAM Ceiling:** 512 MiB.
- **Startup Command:**
  ```powershell
  docker compose up -d openfga infisical
  curl -s http://localhost:8080/healthz
  ```
- **Acceptance:** OpenFGA Zanzibar stores initialized; Infisical Universal Auth token issued.

### Group 3: Telemetry, Observability & Metering Ring (Ring 2)
- **Services:** `otel-collector`, `signoz-metastore-postgres-0`, `ingester`, `openmeter`, `lago-api`.
- **RAM Ceiling:** 1,800 MiB.
- **Startup Command:**
  ```powershell
  docker compose up -d otel-collector openmeter lago-api
  ```
- **Acceptance:** OTel traces ingestion confirmed; Lago webhook receiver ready; OpenMeter Kafka CloudEvent topic active.

### Group 4: Orchestration & Interaction Surface Ring (Rings 3 & 4)
- **Services:** `temporal`, `central-intelligence-reasoning`, `librechat`.
- **RAM Ceiling:** 1,200 MiB.
- **Startup Command:**
  ```powershell
  docker compose up -d temporal librechat
  ```
- **Acceptance:** Temporal namespace ready; LibreChat web interface responding at port 3080.

---

## 4. The 11 Historical Live Integration Scenarios

| Scenario ID | Target Service | Execution Command / Script | Acceptance Criteria |
|---|---|---|---|
| **SC-01** | **OpenFGA** | `pytest tests/integration/test_compose_stack_e2e.py -k test_openfga_live` | Create model, write authorization tuple, check permission, restart OpenFGA container, verify tuple persists without data loss. |
| **SC-02** | **Infisical** | `pytest tests/integration/test_compose_stack_e2e.py -k test_infisical_live` | Authenticate with Universal Auth, store secret in project workspace, restart Infisical container, retrieve secret successfully. |
| **SC-03** | **Lago** | `pytest tests/integration/test_compose_stack_e2e.py -k test_lago_live` | Create customer, assign subscription plan, dispatch usage event via HTTP, verify webhook signature and invoice generation. |
| **SC-04** | **OpenMeter** | `pytest tests/integration/test_compose_stack_e2e.py -k test_openmeter_live` | Ingest CloudEvent token consumption event via Kafka sink, query ClickHouse aggregated balance, verify HTTP 204 response. |
| **SC-05** | **SigNoz** | `pytest tests/integration/test_compose_stack_e2e.py -k test_signoz_live` | Emit OTel trace span from reasoning gateway, query SigNoz ClickHouse trace store, verify span duration and tags appear in query. |
| **SC-06** | **Temporal** | `pytest tests/integration/test_compose_stack_e2e.py -k test_temporal_live` | Launch long-running multi-step agent workflow, issue SIGKILL to worker container mid-execution, start new worker, verify workflow resumes from last checkpoint. |
| **SC-07** | **Supabase / Postgres** | `pytest tests/integration/test_compose_stack_e2e.py -k test_postgres_live` | Execute DDL schema migration via `init-multi-db.sh`, write vector embeddings, execute cosine similarity search, restart container, verify relational & vector integrity. |
| **SC-08** | **Sandbox Isolation** | `pytest tests/integration/test_compose_stack_e2e.py -k test_sandbox_live` | With `SANDBOX_LIVE=1`, execute untrusted Python code inside Docker container, verify Windows host filesystem is unreachable and Job Object / cgroup CPU ceilings hold. |
| **SC-09** | **Kamal Deployment** | `pytest tests/integration/test_compose_stack_e2e.py -k test_kamal_live` | Execute Kamal zero-downtime deployment script in staging container, verify rolling container replacement without 502/503 dropped requests. |
| **SC-10** | **Bytebase** | `pytest tests/integration/test_compose_stack_e2e.py -k test_bytebase_live` | Authenticate against Bytebase API, submit DDL migration issue, approve migration pipeline, verify schema applied to target PostgreSQL database. |
| **SC-11** | **LibreChat to Gateway** | `pnpm --filter @central-intelligence/reasoning run test:e2e-chat` | Launch headless browser script connecting to LibreChat, submit user prompt, verify request traverses to reasoning gateway and streams response tokens back to UI. |

---

## 5. Security, Isolation & Tenant Boundary Testing

1. **Cross-Tenant PostgreSQL Isolation:**
   - Execute parallel transactions from Tenant A (`openfga` role) and Tenant B (`lago` role).
   - Verify Tenant A cannot access Tenant B's tables or catalogs (`PERMISSION DENIED` returned).
2. **ReBAC Zanzibar Authorization Leaks:**
   - Ingest hierarchical organization tree with private documents.
   - Run 1,000 randomized cross-tenant permission check queries; verify 0 permission leaks.
3. **Sandbox Escape & Metacharacter Injection:**
   - Run adversarial payloads from `tests/unit/test_ws03_sandbox_security.py` against running container runner.
   - Verify all host command injection attempts (`cmd.exe`, `powershell`, pipe chains, UNC paths) fail closed.

---

## 6. Endurance, Chaos & Disaster Recovery Exercises

### 6.1 24-Hour Continuous Soak Test (Task S3.5)
- **Target:** Standard profile under simulated multi-tenant load (10 RPS sustained).
- **Metrics Collected:** Memory RSS over time, thread counts, file descriptor leaks, GC pause times.
- **Pass Criteria:**
  - Zero out-of-memory (OOM) terminations.
  - Memory RSS growth <= 5% between hour 2 and hour 24 (no memory leaks).
  - P99 inference routing latency under 150ms.

### 6.2 Chaos Engineering & Fault-Injection Drill (Task S3.6)
- **Scenario 1 (Database Kill):** Send `SIGKILL` to `supabase-db` during heavy fact ingestion. Restart container. Verify PostgreSQL WAL recovery completes cleanly with 0 corrupted pages.
- **Scenario 2 (Valkey Cache Loss):** Flush Valkey cache (`FLUSHALL`). Verify reasoning gateway seamlessly falls back to PostgreSQL relational state without throwing 500 errors.
- **Scenario 3 (Capability Activation Drain Race):** Spawn 50 concurrent worker threads acquiring leases while background daemon drains idle capabilities. Verify 0 deadlocks and 100% Merkle audit log integrity.

### 6.3 Backup, Snapshot & Rollback Drills (Task S4.4)
- Take full filesystem and database snapshot using `cognitive/memory/snapshots/manager.py`.
- Inject corrupted/poisoned memory facts into fact store.
- Execute automated rollback command (`rollback_guard.py`).
- Verify state is restored to pre-poisoning snapshot within 30 seconds.

---

## 7. Clean-Install & Upgrade Verification (Task S4.2)

1. **Clean Bootstrap Drill:**
   - Provision fresh Ubuntu 24.04 / Debian 12 environment with only Docker and Python 3.12 installed.
   - Clone repository, copy `.env.example` to `.env`, run `./scripts/bootstrap.sh`.
   - Verify all required configuration files, SSL certificates, and database schemas initialize without manual intervention in under 3 minutes.
2. **Upgrade & Migration Reversibility Drill (Task S4.3):**
   - Apply DDL schema migration via Bytebase / Alembic.
   - Execute down-migration / rollback.
   - Verify zero orphan tables or broken foreign keys.

---

## 8. Release Candidate (RC1) Entry Gate Criteria

Promotion from Stage S4 to Stage S5 (Release Candidate 1) requires 100% of the following:

- [ ] All 11 historical live integration scenarios pass with genuine live services in disposable staging.
- [ ] 24-hour continuous soak test completes with zero OOM events and stable RSS.
- [ ] Chaos drills complete: WAL recovery, cache fallback, and worker crash resumption verified.
- [ ] Zero active P0 or P1 defects in `docs/CRITICAL_DEFECT_REGISTER.md`.
- [ ] Clean install script verified on fresh VM instance.
- [ ] Independent security lead and QA lead sign-off.

---

## 9. Critical-Path Effort & Duration Estimates

| Scenario / Trajectory | Optimistic ETA | Most Likely ETA | Conservative ETA |
|---|:---:|:---:|:---:|
| **Stage S2 (Live 11-Service Integrations)** | 24 hours | 48 hours | 96 hours |
| **Stage S3 (Reliability, Soak & Chaos)** | 20 hours | 40 hours | 80 hours |
| **Stage S4 (Deployment, Recovery & Upgrades)** | 16 hours | 32 hours | 64 hours |
| **Stage S5 (RC1 Tagging & Final Release Gate)** | 12 hours | 24 hours | 48 hours |
| **Stage S6 (Production Readiness & Sign-Off)** | 8 hours | 16 hours | 32 hours |
| **TOTAL TESTING & OPERATIONAL PHASE** | **80 hours (~2.0 wks)** | **160 hours (~4.0 wks)** | **320 hours (~8.0 wks)** |

---

## 10. Conclusion & Execution Authorization

With the completion and sign-off of the v1 build, Central Intelligence is officially handed over to the QA and Infrastructure teams to execute this testing plan in the designated staging environment.
