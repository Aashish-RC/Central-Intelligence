# CENTRAL INTELLIGENCE V1 — S2 INTEGRATION CLOSURE & VERIFICATION AUDIT

**Author:** QA Engineering Lead, Principal Architect & Security Verifier  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `af93f635fe225be0023b851bab982a52fa69b67c` (`af93f63`)  
**Workspace:** `D:\central-intelligence`  
**Date:** 2026-11-18  
**Audit Scope:** Dedicated Live Integration Verification (Scenarios SC-01 through SC-11)  
**Overall Status:** **STAGE S2 ADVANCED — 6/11 GENUINE LIVE PASSES, 1 SIMULATED, 4 BLOCKED (16 GB STAGING ENVIRONMENT REQUIRED). STAGE S2 CANNOT BE CLOSED UNTIL REMAINING 4 STAGING SCENARIOS COMPLETE ON APPROVED INFRASTRUCTURE.**

---

## 1. Executive Summary & Verification Ledger

Under strict operational constraints ($0.00 spend, never modify production data, preserve volume durability, 8 GB laptop memory protection):
- **Genuine Live Verified Passes:** **6 of 11** (`SC-01`, `SC-02`, `SC-06`, `SC-07`, `SC-08`, `SC-10`).
- **Simulated (Mocked) Passes:** **1 of 11** (`SC-09` Kamal command sequence — preserved; actual server deployment deferred).
- **Blocked Scenarios:** **4 of 11** (`SC-03` Lago, `SC-04` OpenMeter, `SC-05` SigNoz, `SC-11` LibreChat — require approved 16 GB staging environment).
- **Failed Scenarios:** **0** (All active tests passed clean; all identified defects reproduced, classified, and fixed).
- **Auxiliary Live Passes (Foundation):** **4 of 4** (Valkey 8.0 wire roundtrip, Qdrant 1.20 collection & query, Apache AGE 1.6 graph execution, Temporal 1.10 echo).
- **Total Monitored Memory:** **1,116.3 MiB** across 8 running containers with **>800 MB** host physical RAM headroom maintained at all times.

---

## 2. Exhaustive Scenario Evidence Table (SC-01 through SC-11)

| Scenario | Status | Execution Command & Environment | Verification (Actual Service Behavior) | Durability Scope | Security (Auth & Isolation) | Resources Measured | Defects & Remediation | Next Action / Remaining Requirement |
|---|:---:|---|---|---|---|:---:|---|---|
| **SC-01: OpenFGA** | **PASS** | `python` live script & `pytest tests/integration/test_compose_stack_e2e.py::test_openfga_persists_across_python_restart -m requires_provisioned_services` on Windows / WSL2 Docker | Disposable store `01M7NCC0JY379688V9JRGYPT64`, model `01M7NCC0QKBWNQG6GWG14HJZMJ` created. Written tuple `user:6e023f57` viewer `document:7fa3577e`. Pre-restart check `allowed=True`. Executed `docker restart central-openfga`. Health check polled to `{"status":"SERVING"}`. Post-restart check `allowed=True`. Negative unauthorized check `allowed=False`. | **Container Restart + Volume-Backed Datastore** | Pre-shared key / local HTTP boundary; multi-tenant store isolation verified. | RAM: 58.1 MiB<br>CPU: 0.85% | **DEF-10**: OpenFGA previously ran with ephemeral `OPENFGA_DATA_STORE_ENGINE=memory`. Migrated schema via `openfga migrate` and attached persistent PostgreSQL datastore `central-supabase-db:5432/openfga`. | S2 acceptance met. Ready for production configuration. |
| **SC-02: Infisical** | **PASS** | `python` live script & `pytest tests/integration/test_compose_stack_e2e.py::test_infisical_persists_across_python_restart -m requires_provisioned_services` on port 8083 | Initialized admin `admin@example.com`, established org-scoped JWT, created workspace `central-intelligence-vault` (`cb86582f-...`), created machine identity `central-agent`, attached Universal Auth (`client_id: 68eff620-...`), generated Client Secret, stored raw secret `TEST_LIVE_SECRET`. Executed `docker restart central-infisical`. Re-authenticated via Universal Auth post-restart; retrieved secret `super-secret-value-live-xyz` identical. | **Container Restart + Volume-Backed Storage** | Universal Auth Machine Identity + AES-256-GCM vault encryption; consolidated database isolation on `infisical` DB & Valkey DB 2. | RAM: 178.4 MiB<br>CPU: 0.41% | **DEF-13**: `InfisicalAdapter._ensure_live_backend` probed 404 path `/api/v1/status` instead of `/api/status`, and module singleton eagerly authenticated during import. Added v3 raw secret fallback and deferred singleton auth. | S2 acceptance met. Rotate test credentials prior to production deployment. |
| **SC-03: Lago** | **BLOCKED** | `pytest tests/integration/test_compose_stack_e2e.py::test_lago_persists_across_python_restart -m requires_provisioned_services` | Deferred to 16 GB staging environment. | N/A (Blocked) | Requires AGPL-3.0 quarantine network isolation and `LAGO_API_KEY`. | N/A (Not started) | None (Environmental constraint). | Provision 16 GB disposable staging environment (e.g. GitHub Codespace) to run Lago API, Sidekiq workers, and Redis without host OOM. |
| **SC-04: OpenMeter** | **BLOCKED** | `pytest tests/integration/test_compose_stack_e2e.py::test_openmeter_persists_across_python_restart -m requires_provisioned_services` | Deferred to 16 GB staging environment. | N/A (Blocked) | CloudEvents ingestion authentication & ClickHouse analytical query isolation. | N/A (Not started) | None (Environmental constraint). | Provision 16 GB disposable staging environment with ClickHouse and Kafka/Redpanda cluster. |
| **SC-05: SigNoz** | **BLOCKED** | `pytest tests/integration/test_compose_stack_e2e.py::test_signoz_persists_across_python_restart -m requires_provisioned_services` | Deferred to 16 GB staging environment. | N/A (Blocked) | OpenTelemetry Collector gRPC/HTTP endpoint token authentication. | N/A (Not started) | None (Environmental constraint). | Provision 16 GB disposable staging environment to support SigNoz ClickHouse, ZooKeeper/Keeper, query service, and OTel collector (~4–8 GB footprint). |
| **SC-06: Temporal** | **PASS** | `pytest tests/integration/test_compose_stack_e2e.py::test_temporal_workflow_survives_worker_restart -m requires_provisioned_services` on port 7233 | 5-node DAG workflow started (`CIDagWorkflow`). Worker 1 was killed via `SIGKILL` during active execution. Worker 2 started fresh, reconnected to Temporal cluster, replayed event history from server, and executed all 5 tasks to `COMPLETED` without duplicate activity side effects. | **Process Restart + Event History Replay** | mTLS/namespace isolation on Temporal server cluster. | RAM: 168.0 MiB<br>CPU: 1.28% | None. Baseline test passed clean. | S2 acceptance met. |
| **SC-07: PostgreSQL / pgvector** | **PASS** | `python` live script & `pytest tests/integration/test_compose_stack_e2e.py::test_supabase_relational_and_vector_persist -m requires_provisioned_services` on port 5432 | Created isolated schema `e2e_sc07_759408bd`; inserted relational rows and 3D vector embeddings across `tenant-alpha` and `tenant-beta`. Verified cosine similarity search (`top_k=1`, distance `5.1e-5`). Executed `docker restart central-supabase-db`. Reconnected post-restart; re-verified vector query accuracy, relational rows, and tenant boundary enforcement. Cleaned up test schema. | **Container Restart + Named Volume Storage (`central-intelligence_supabase_data`)** | PostgreSQL role permissions, isolated schema namespaces, and tenant ID query filters. | RAM: 185.1 MiB<br>CPU: 0.05% | **DEF-11**: Container was originally mounted on `/var/lib/postgresql/data` with in-memory `tmpfs`. Recreated container mounting named Docker volume `central-intelligence_supabase_data`. | S2 acceptance met. Volume durability confirmed. |
| **SC-08: Sandbox** | **PASS** | `pytest tests/integration/test_c3_sandbox_isolation_live.py -m live -v` & `test_sandbox_executes_real_python` | 12/12 C3 runtime isolation controls passed: real Python code executed (`print(2+2)` -> `4`), host environment isolation verified (Linux container on Windows host), read-only rootfs enforced, host filesystem mounts blocked, drop-all capabilities (`CapEff=0`), memory and CPU limits enforced. | **Container Execution Isolation** | Zero-trust container sandbox, non-root user execution, drop all Linux capabilities (`CapEff=0000000000000000`). | RAM: Bounded to 128 MiB cgroup limit | None. Baseline test passed clean. | S2 acceptance met. |
| **SC-09: Kamal** | **SIMULATED** | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_kamal_deployment_command_sequence_is_simulated -v` | Executed complete deployment phase sequence: lock acquire -> registry push -> app boot -> proxy boot -> app stop -> lock release. Verified correct execution ordering and failure recovery behavior. | **Simulated Execution** | SSH key authentication and container registry credentials simulated in test harness. | CPU/RAM negligible (local process) | None. Preserved as simulated per explicit operating instruction. | Requires authorized external disposable Linux server with SSH access and Docker daemon for genuine live deployment verification. Left SIMULATED/BLOCKED until target provided. |
| **SC-10: Bytebase** | **PASS** | `pytest tests/integration/test_compose_stack_e2e.py::test_bytebase_migration_executes_real_ddl -m requires_provisioned_services` & negative tests on port 5678 | Initialized admin user `admin@example.com`, retrieved JWT token, registered Postgres instance, configured environment `environments/test`. Executed real DDL migration: Sheet upload -> Plan creation -> Issue generation -> Rollout `tasks:batchRun`. Verified table created in PostgreSQL `information_schema.tables`. Executed live rollback and verified cleanup. Verified unauthenticated HTTP 401 rejection and unapproved migration `PermissionError` gate rejection. | **Container Execution + Live Database DDL Rollout** | Bytebase JWT Bearer authentication, RBAC review gates, non-superuser Postgres data source credentials. | RAM: 368.2 MiB<br>CPU: 0.52% | **DEF-12**: Bytebase 3.x lacks `/v1/sql/execute` and returned 401 on uninitialized workspace. Added admin bootstrap, modernized `BytebaseAdapter` to use Bytebase 3.x Sheet/Plan/Issue/Rollout batchRun API with rollout readiness polling. | S2 acceptance met. DDL rollout verified. |
| **SC-11: LibreChat → Gateway** | **BLOCKED** | `pytest tests/integration/test_compose_stack_e2e.py::test_librechat_routes_to_reasoning_gateway -m requires_provisioned_services` | Deferred to 16 GB staging environment. | N/A (Blocked) | JWT session authentication, reverse-proxy gateway routing, and tenant boundary enforcement. | N/A (Not started) | None (Environmental constraint). | Provision 16 GB disposable staging environment with LibreChat, MongoDB, Meilisearch, and genuine reasoning endpoint. |

---

## 3. Discovered Defects Ledger & Resolutions

During dedicated S2 integration recovery, four critical defects were identified, reproduced, classified, and fixed:

1. **DEF-10 (OpenFGA Ephemeral In-Memory Storage):**
   - *Root Cause:* Container was running with `OPENFGA_DATA_STORE_ENGINE=memory`. Container restarts wiped all stores and authorization tuples.
   - *Fix:* Executed `openfga migrate` against consolidated PostgreSQL and restarted container with `--datastore-engine postgres` connecting to `central-supabase-db:5432/openfga`.
   - *Verification:* Container restarted; authorization tuple persisted and evaluated correctly post-restart.
2. **DEF-11 (PostgreSQL Container In-Memory tmpfs Data Storage):**
   - *Root Cause:* `central-supabase-db` was originally started mounting `/var/lib/postgresql/data` on volatile `tmpfs` RAM, risking total data loss upon container restart/recreation.
   - *Fix:* Created named Docker volume `central-intelligence_supabase_data` and recreated the database container attaching this persistent volume.
   - *Verification:* Created relational and vector data in isolated schema, executed `docker restart central-supabase-db`, confirmed data persisted and vector search executed accurately post-restart.
3. **DEF-12 (Bytebase Uninitialized Workspace & Incompatible Legacy API):**
   - *Root Cause:* Bytebase 3.24.1 returned HTTP 401 (`access token not found`) on uninitialized workspace, and `BytebaseAdapter` called non-existent `/v1/sql/execute` endpoint.
   - *Fix:* Bootstrapped admin user, acquired JWT token, configured database environment, and modernized `BytebaseAdapter` to use the official Bytebase 3.x CI/CD flow: Sheet -> Plan -> Issue -> Rollout batchRun with readiness polling.
   - *Verification:* Real DDL executed live in PostgreSQL, verified in information schema, rolled back, and verified negative security gates (HTTP 401 unauthenticated, `PermissionError` unapproved).
4. **DEF-13 (Infisical Health Endpoint Path Mismatch & Singleton Eager Auth):**
   - *Root Cause:* `InfisicalAdapter._ensure_live_backend` probed `/api/v1/status` (returning HTTP 404 in Infisical v0.167.8) rather than `/api/status`, and module-level singleton eagerly authenticated during Python import.
   - *Fix:* Updated health check with `/api/status` fallback, implemented `/api/v3/secrets/raw` secret lifecycle with legacy v1 fallback, and deferred singleton auth checks.
   - *Verification:* Verified machine identity creation, Universal Auth Client Secret generation, secret storage, container restart persistence, and `test_infisical_persists_across_python_restart` pytest execution.

---

## 4. Final Assessment: Can Stage S2 Be Closed?

### S2 Closure Criteria
Under the governing test plan (`docs/V1_TEST_EXECUTION_PLAN.md`), Stage S2 requires **11/11 genuinely verified scenarios** meeting all approved acceptance criteria.

### Status Determination
- **Current Genuine Live Passes:** **6 of 11 (54.5%)**
- **Simulated:** **1 of 11 (9.1%)**
- **Blocked on Hardware/Staging:** **4 of 11 (36.4%)**

### Verdict
**STAGE S2 CANNOT BE CLOSED TODAY.**

Declaring 11/11 complete at this stage would violate the mandatory instruction:
> *"Only declare S2 COMPLETE — 11/11 VERIFIED if every mandatory scenario has genuinely met its approved acceptance criteria. Otherwise continue safe testing and identify the exact blockers."*

### Exact Requirements to Achieve 11/11 and Close Stage S2:
1. **Provision 16 GB Disposable Staging Environment (GitHub Codespaces):**
   - Required for `SC-03` (Lago), `SC-04` (OpenMeter), `SC-05` (SigNoz), and `SC-11` (LibreChat).
   - The 8 GB local PC has ~800 MB free RAM and cannot safely run Kafka, ClickHouse, Meilisearch, MongoDB, and SigNoz without kernel OOM lockups.
2. **Authorized Disposable Deployment Target Server:**
   - Required for `SC-09` (Kamal) to transition from SIMULATED to a genuine live pass.
   - Requires an authorized disposable Linux staging server with SSH credentials and Docker daemon.
