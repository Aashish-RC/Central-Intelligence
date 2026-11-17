# CENTRAL INTELLIGENCE V1 — INTEGRATION EXECUTION STATUS & STAGING AUDIT

**Author:** QA Lead, Platform Reliability Engineer & Security Lead  
**Scope:** Status of All 11 Live Integration Scenarios, Resource Auditing, and Staging Blockers  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **AUTHORITATIVE EXECUTION LEDGER — STAGE S2 ACTIVE**  

---

## 1. Executive Summary & Verification Ledger

Under strict operational constraints ($0.00 spend, zero mock leakage, preservation of host developer memory, no unapproved external deployments):
- **Genuine Live Verified Passes:** **6 of 11** (`SC-01`, `SC-02`, `SC-06`, `SC-07`, `SC-08`, `SC-10`).
- **Simulated (Mocked) Passes:** **1 of 11** (`SC-09` Kamal command sequence — preserved as simulated; live server execution deferred).
- **Blocked on 16 GB Staging:** **4 of 11** (`SC-03` Lago, `SC-04` OpenMeter, `SC-05` SigNoz, `SC-11` LibreChat).
- **Auxiliary Live Passes (Foundation):** **4 of 4** (Valkey 8.0, Qdrant 1.20, Apache AGE 1.6, Temporal Echo).
- **Host Memory Safety:** Currently running 8 active containers inside Docker Desktop WSL2 totaling **1,116.3 MiB RAM**, maintaining **>700 MB physical RAM headroom** on the 8 GB host machine.

---

## 2. Granular Scenario Ledger (SC-01 through SC-11)

### 2.1 Verified Genuine Live Scenarios (6/11)

#### SC-01: OpenFGA Relationship Authorization
- **Status:** **PASS (GENUINE LIVE)**
- **Image / Target:** `openfga/openfga:v1.22.1` on port 8081.
- **Verification Evidence:** Model `01M7NCC0QKBWNQG6GWG14HJZMJ` created. Auth tuple `user:6e023f57 viewer document:7fa3577e` written. Pre-restart check `allowed=True`. Executed hard `docker restart central-openfga`. Health endpoint polled to `{"status":"SERVING"}`. Post-restart check evaluated `allowed=True`. Negative unauthorized check evaluated `allowed=False`.
- **Durability Scope:** Container restart + volume-backed datastore on PostgreSQL `central-supabase-db:5432/openfga`.
- **Measured RAM:** **19.4 MiB** (Go runtime).

#### SC-02: Infisical Secrets Vault & Machine Identity
- **Status:** **PASS (GENUINE LIVE)**
- **Image / Target:** `infisical/infisical:v0.167.8` on port 8083.
- **Verification Evidence:** Initialized admin `admin@example.com`, acquired org JWT, created workspace `central-intelligence-vault`, provisioned machine identity `central-agent`, attached Universal Auth (`client_id: 68eff620-...`), generated Client Secret, stored raw secret `TEST_LIVE_SECRET`. Hard restart via `docker restart central-infisical`. Re-authenticated via Universal Auth; secret retrieved with identical plaintext.
- **Durability Scope:** Container restart + volume-backed database on `central-supabase-db:5432/infisical` and Valkey DB 2.
- **Measured RAM:** **178.4 MiB** (Node.js runtime).

#### SC-06: Temporal Workflow Crash Recovery & Replay
- **Status:** **PASS (GENUINE LIVE)**
- **Image / Target:** `temporalio/temporal:1.10.0` on port 7233.
- **Verification Evidence:** Started 5-node DAG workflow (`CIDagWorkflow`). Worker 1 killed via `SIGKILL` during active execution. Worker 2 started fresh, reconnected to cluster, replayed event history from server, and executed all 5 tasks to `COMPLETED` without duplicate activity side effects.
- **Durability Scope:** Worker crash recovery + server-side event history replay.
- **Measured RAM:** **176.9 MiB** (Go runtime).

#### SC-07: PostgreSQL & pgvector Relational Persistence
- **Status:** **PASS (GENUINE LIVE)**
- **Image / Target:** `supabase/postgres:15.1.1.78` on port 5432.
- **Verification Evidence:** Created isolated schema `e2e_sc07_759408bd`. Inserted relational rows and 3D vector embeddings across `tenant-alpha` and `tenant-beta`. Cosine similarity search verified (`top_k=1`, distance `5.1e-5`). Hard restart via `docker restart central-supabase-db`. Post-restart re-verified vector query accuracy, relational rows, and tenant boundary enforcement.
- **Durability Scope:** Named Docker volume storage `central-intelligence_supabase_data`.
- **Measured RAM:** **174.9 MiB** (PostgreSQL 15 + pgvector).

#### SC-08: Sandbox Container Runtime Isolation
- **Status:** **PASS (GENUINE LIVE)**
- **Target:** Ephemeral `python:3.12-slim` container on host Docker daemon.
- **Verification Evidence:** Executed actual Python code (`python3 -c 'print(2+2)'` -> `4`). All 12 C3 security controls verified: Linux container execution on host, zero capabilities (`CapEff=0000000000000000`), read-only rootfs (`--read-only`), blocked host filesystem mounts, network disabled (`--network none`), memory capped (128 MiB cgroup limit).
- **Durability Scope:** Per-execution ephemeral container teardown.
- **Measured RAM:** Ephemeral (capped at 128 MiB).

#### SC-10: Bytebase Authenticated DDL Rollout
- **Status:** **PASS (GENUINE LIVE)**
- **Image / Target:** `bytebase/bytebase:3.24.1` on port 5678.
- **Verification Evidence:** Admin user initialized, JWT token acquired, database environment configured. Real DDL migration executed via official Bytebase 3.x CI/CD flow: Sheet -> Plan -> Issue -> Rollout `tasks:batchRun`. Verified table creation in PostgreSQL `information_schema.tables`. Executed live rollback and verified table removal. Verified negative security gates (HTTP 401 unauthenticated, `PermissionError` unapproved).
- **Durability Scope:** Container execution + live transactional DDL execution on PostgreSQL.
- **Measured RAM:** **368.2 MiB** (Go binary + embedded assets).

---

### 2.2 Simulated Scenario (1/11)

#### SC-09: Kamal Zero-Downtime Deployment
- **Status:** **SIMULATED PASS (PRESERVED AS SIMULATED)**
- **Tool:** Kamal CLI orchestration wrapper (`platform_infra/release/ci/kamal_adapter.py`).
- **Verification Evidence:** Verified complete command sequence ordering: `kamal lock acquire` -> `kamal registry push` -> `kamal app boot` -> `kamal proxy boot` -> `kamal app stop` -> `kamal lock release`. Failure recovery and rollback hooks tested.
- **Why Kept Simulated:** Kamal is a deployment-method CLI tool, not a runtime service. Genuine live deployment requires an authorized external Linux server with root SSH keys and container registry credentials. Per operating instructions, no external deployments are performed without explicit authorization.

---

### 2.3 Blocked Scenarios Awaiting 16 GB Staging (4/11)

#### SC-03: Lago Subscription Billing Engine
- **Status:** **BLOCKED (Requires 16 GB Staging)**
- **Required Stack:** 5 containers (`lago` Rails API, `lago-worker` Sidekiq, `lago-migrate`, `lago-postgres`, `lago-redis`).
- **Resource Requirement:** ~600–800 MiB RAM baseline.
- **Blocking Constraint:** Attempting to start the Rails API and Sidekiq worker alongside existing core containers on the 8 GB host risks kernel OOM thrashing.
- **Readiness:** Code is 100% written (`LagoAdapter`). Unit tests and offline billing tests in `test_ws05_billing_licensing.py` pass. Preflight fail-closed checks verified. Ready to execute immediately upon allocation of a 16 GB staging runner.

#### SC-04: OpenMeter Real-Time Token Metering
- **Status:** **BLOCKED (Requires 16 GB Staging)**
- **Required Stack:** 9 containers (`openmeter` server, `openmeter-clickhouse`, `openmeter-postgres`, `openmeter-redis`, 4 worker daemons, Apache Kafka).
- **Resource Requirement:** ~1.8–2.5 GiB RAM baseline.
- **Blocking Constraint:** Apache Kafka (JVM) and ClickHouse (OLAP) cannot run concurrently on an 8 GB host with ~700 MB free RAM.
- **Readiness:** Code is 100% written (`OpenMeterAdapter`). CloudEvents 1.0 JSON generation and local accumulator verified in unit tests. Ready for execution in 16 GB staging.

#### SC-05: SigNoz Distributed APM & Telemetry
- **Status:** **BLOCKED (Requires 16 GB Staging)**
- **Required Stack:** 7 containers (`signoz-telemetrystore-clickhouse`, `signoz-telemetrykeeper`, `signoz-metastore-postgres`, `signoz-ingester`, `signoz-frontend`, `otel-collector`).
- **Resource Requirement:** ~2.5–4.0 GiB RAM baseline.
- **Blocking Constraint:** ClickHouse cluster and ClickHouse Keeper require massive memory allocation, causing WSL2 Docker engine crash on local host.
- **Readiness:** Code is 100% written (`SigNozAdapter`). OpenTelemetry trace generation and local span logging verified. Ready for execution in 16 GB staging.

#### SC-11: LibreChat Web Chat UI Gateway Route
- **Status:** **BLOCKED (Requires 16 GB Staging)**
- **Required Stack:** 3 containers (`librechat` Node.js, `librechat-mongodb`, `meilisearch`).
- **Resource Requirement:** ~400–500 MiB RAM baseline.
- **Blocking Constraint:** Memory headroom limit on local PC.
- **Readiness:** Configuration mounted (`librechat.yaml`). Gateway proxy adapter verified in unit tests. Ready for execution in 16 GB staging.

---

## 3. Auxiliary Live Passes (Foundation)

| Service | Version / Tag | Measured RAM | CPU % | Operational Verification |
|---|---|:---:|:---:|---|
| **Valkey** | `valkey/valkey:8.0.2-alpine` | **6.5 MiB** | 0.67% | Redis wire protocol ping/pong, key expiration, working memory session turns. |
| **Qdrant** | `qdrant/qdrant:v1.20.0` | **57.2 MiB** | 0.20% | Collection initialization, 1536-dim vector indexing, payload metadata filter queries. |
| **Apache AGE** | `apache/age:release_PG16_1.6.0` | **82.6 MiB** | 0.01% | `LOAD 'age';` Cypher graph creation, entity vertex/edge traversal. |
| **Temporal Echo** | `temporalio/temporal:1.10.0` | — | — | Client-to-server workflow registration and execution roundtrip. |

---

## 4. Staging Environment Assessment & Zero-Spend Compliance

1. **Free Staging Availability:** An inspection of the workspace and environment confirmed that no free 16 GB staging environment (such as a 4-core / 16 GB GitHub Codespace) is currently active or authenticated for this session.
2. **Zero-Spend Constraint:** Under Principle 9 ("Zero mandatory paid spending remains a fundamental constraint"), no paid cloud instances (AWS EC2, GCP Compute Engine, Azure VMs) were provisioned.
3. **Local PC Protection:** The local host was kept strictly within its safe operational limits: 8 containers running, 1,116.3 MiB total RAM, zero swap thrashing, zero dropped requests.
