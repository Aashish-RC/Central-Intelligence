# CENTRAL INTELLIGENCE V1 — LIVE INTEGRATION TEST RESULTS (STAGE S2)

**Author:** QA Engineering Lead & Infrastructure Verifier  
**Target:** Dedicated Live Integration Testing (Stage S2)  
**Date:** 2026-11-18  
**Working Revision:** `af93f635fe225be0023b851bab982a52fa69b67c` (`af93f63`)  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Execution Environment:** Local Hybrid Staging (Windows 11 x64, WSL2 Engine, Docker 29.9.2, Python 3.12.12 venv)  
**Status:** **STAGE S2 ADVANCED — 6/11 GENUINE PASSES, 1 SIMULATED, 4 BLOCKED (16 GB STAGING ENVIRONMENT REQUIRED)**  

---

## 1. Executive Summary

In accordance with `docs/V1_TEST_EXECUTION_PLAN.md` and strict operating constraints:
- Zero paid spending incurred ($0.00).
- Complete enterprise stack was **NOT** launched simultaneously on the 8 GB host to prevent host OOM lockups.
- Services were brought up sequentially and connected to consolidated backend instances (Postgres, Valkey).
- Total active container RAM consumption remained bounded at **~1.1 GiB** across running services with zero swap thrashing.
- Real services were tested; mocked/simulated tests are strictly distinguished from genuine live passes.
- Durability guarantees have been reconciled across Python process restart, service process restart, container restart, and persistent volume recovery.

### Results Overview
- **Genuine Live Integration Passes:** **6 of 11** (OpenFGA, Infisical, Temporal, PostgreSQL/pgvector, Sandbox Container Isolation, Bytebase).
- **Auxiliary Live Passes (Foundation):** **4 of 4** (Valkey Redis wire roundtrip, Qdrant vector store, Apache AGE graph adapter, Temporal basic echo).
- **Simulated (Mocked) Passes:** **1 of 11** (Kamal deployment sequence).
- **Blocked Scenarios:** **4 of 11** (Lago, OpenMeter, SigNoz, LibreChat — require approved disposable 16 GB staging environment).
- **Failed Scenarios (Defects):** **0** (All active tests passed clean; all discovered integration defects resolved).

---

## 2. Durability Classification Framework

To eliminate ambiguity, test verification strictly records durability guarantees across distinct boundaries:
1. **Python Process Restart:** Verifies client state does not rely on in-process Python memory; subsequent fresh Python processes retrieve identical state.
2. **Service Process Restart:** Verifies the daemon process within the container persists state to internal storage.
3. **Container Restart:** Verifies the service survives `docker restart <container>` without losing configuration, authentication, or application data.
4. **Container Recreation:** Verifies a destroyed and freshly recreated container (`docker rm` -> `docker run`) reading the same volume retains all state.
5. **Persistent Volume Recovery:** Verifies storage is backed by a named Docker volume (`central-intelligence_supabase_data`) rather than tmpfs/ephemeral container layer, surviving complete engine restart.

---

## 3. The 11 Live Integration Scenarios Matrix

| ID | Target Service | Service Version / Image | Exact Test Command | Durability Verified | Execution Evidence | Status | Defects Discovered & Remediation |
|---|---|---|---|:---:|---|:---:|---|
| **SC-01** | **OpenFGA** | `openfga/openfga:v1.22.1` (port 8081) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_openfga_persists_across_python_restart -v` & Live Container Restart Verification | **Container Restart + Volume-Backed Datastore** | Created disposable store `01M7NCC0JY379688V9JRGYPT64`, model `01M7NCC0QKBWNQG6GWG14HJZMJ`; wrote tuple `viewer`; pre-restart check `allowed=True`; executed `docker restart central-openfga`; polled `healthz` to SERVING; post-restart check returned `allowed=True`; unauthorized user check returned `allowed=False`. | **✅ PASSED (GENUINE LIVE)** | Previously ran with in-memory datastore (`OPENFGA_DATA_STORE_ENGINE=memory`). Migrated schema and attached PostgreSQL engine backed by persistent volume. |
| **SC-02** | **Infisical** | `infisical/infisical:v0.167.8` (port 8083) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_infisical_persists_across_python_restart -v` & Live Container Restart Verification | **Container Restart + Volume-Backed Storage** | Initialized disposable admin, established org-scoped JWT, created workspace `central-intelligence-vault`, configured Machine Identity `central-agent` with Universal Auth, minted Client Secret, stored raw secret `TEST_LIVE_SECRET`; executed `docker restart central-infisical`; re-authenticated via Universal Auth post-restart and verified retrieved secret value matches. | **✅ PASSED (GENUINE LIVE)** | Fixed `InfisicalAdapter._ensure_live_backend` status endpoint from 404 `/api/v1/status` to `/api/status`, added v3 raw secret fallback, deferred singleton instantiation. |
| **SC-03** | **Lago** | `lago-api:3000` (AGPL-3.0) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_lago_persists_across_python_restart -v` | Deferred | Multi-tier Rails API, Sidekiq workers, and Redis exceed 8 GB host memory threshold. | **🟡 BLOCKED** | Memory constraint on 8 GB laptop; requires 16 GB disposable staging environment. |
| **SC-04** | **OpenMeter** | `openmeter:8888` | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_openmeter_persists_across_python_restart -v` | Deferred | OpenMeter + Kafka/Redpanda + ClickHouse cluster exceeds 8 GB host memory headroom. | **🟡 BLOCKED** | Requires 16 GB disposable staging environment for ClickHouse/Kafka cluster. |
| **SC-05** | **SigNoz** | `signoz:3301` | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_signoz_persists_across_python_restart -v` | Deferred | SigNoz telemetry cluster (ClickHouse, ZooKeeper/Keeper, OTel Collector) requires 4–8 GB RAM. | **🟡 BLOCKED** | Enterprise observability cluster deferred to 16 GB staging environment. |
| **SC-06** | **Temporal** | `temporalio/temporal:1.10.0` (port 7233) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_temporal_workflow_survives_worker_restart -v` | **Process Restart + Event History Replay** | 5-node DAG workflow started (`CIDagWorkflow`). Worker 1 SIGKILL'd mid-execution. Worker 2 restarted, replayed workflow history from Temporal server, executed all 5 steps to completion. | **✅ PASSED (GENUINE LIVE)** | None. Server-side event replay and worker recovery verified. |
| **SC-07** | **PostgreSQL / pgvector** | `supabase/postgres:15.1.1.78` (port 5432) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_supabase_relational_and_vector_persist -v` & Live Container Restart Verification | **Container Restart + Volume-Backed Storage** | Verified named volume `central-intelligence_supabase_data`. Created isolated schema `e2e_sc07_759408bd`; inserted relational and vector records across tenants; verified cosine distance retrieval; executed `docker restart central-supabase-db`; reconnected post-restart; re-verified vector query accuracy, relational rows, and tenant isolation; dropped test schema. | **✅ PASSED (GENUINE LIVE)** | Container was previously started with `--tmpfs /var/lib/postgresql/data`. Recreated container mounting persistent named Docker volume. |
| **SC-08** | **Sandbox Isolation** | `python:3.12-slim` container on local Docker daemon | `pytest tests/integration/test_c3_sandbox_isolation_live.py -m live -v` & `test_sandbox_executes_real_python` | **Container Execution Isolation** | 12/12 C3 runtime isolation controls passed: real code computed (`print(2+2)` -> `4`), platform isolation verified (Linux container vs Windows host), read-only rootfs enforced, host mounts blocked, zero privilege escalation (`CapEff=0`), CPU & memory ceilings held. | **✅ PASSED (GENUINE LIVE)** | None. Container execution is completely unmocked and isolated. |
| **SC-09** | **Kamal Deployment** | N/A (Docker / Kamal CLI) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_kamal_deployment_command_sequence_is_simulated -v` | Simulated Execution | Executed complete deploy phase sequence: `kamal lock acquire` -> `kamal registry push` -> `kamal app boot` -> `kamal proxy boot` -> `kamal app stop` -> `kamal lock release`. Phase marked COMPLETED. | **🟡 SIMULATED (Mocked)** | Real server deployment requires authorized disposable target server with SSH credentials. |
| **SC-10** | **Bytebase** | `bytebase/bytebase:3.24.1` (port 5678) | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_bytebase_migration_executes_real_ddl -v` & Negative Tests | **Container Execution + Live Postgres DDL Rollout** | Resolved 401: provisioned admin user, acquired JWT, registered Postgres instance, created Sheet -> Plan -> Issue -> Rollout `tasks:batchRun`, verified real table created in Postgres `information_schema.tables`, executed rollback, cleaned up. Verified 401 rejection for unauthenticated calls and `PermissionError` for unapproved migrations. | **✅ PASSED (GENUINE LIVE)** | Bytebase 3.x lacks `/v1/sql/execute`. Modernized adapter to use Sheet/Plan/Issue/Rollout batchRun API with rollout readiness polling. |
| **SC-11** | **LibreChat to Gateway** | `librechat-dev` + reasoning gateway | `pytest tests/integration/test_compose_stack_e2e.py -m requires_provisioned_services -k test_librechat_routes_to_reasoning_gateway -v` | Deferred | LibreChat container, MongoDB, Meilisearch, and real inference upstream exceed 8 GB host memory safe threshold. | **🟡 BLOCKED** | Staging multi-container footprint requires 16 GB staging environment. |

---

## 4. Auxiliary Live Stack Integrations (Foundation Ring)

| Service | Version / Port | Test Name | Execution Result |
|---|---|---|:---:|
| **Valkey** | `valkey:8.0.2-alpine` (port 6379) | `test_valkey_redis_wire_roundtrip_e2e` | **✅ PASSED (LIVE)** |
| **Qdrant** | `qdrant/qdrant:v1.20.0` (port 6333) | `test_qdrant_vector_roundtrip_e2e` | **✅ PASSED (LIVE)** |
| **Apache AGE** | `apache/age:release_PG16_1.6.0` (port 5433) | `test_postgres_apache_age_graph_adapters_e2e` | **✅ PASSED (LIVE)** |
| **Temporal Echo** | `temporal:1.10.0` (port 7233) | `test_temporal_workflow_execution_e2e` | **✅ PASSED (LIVE)** |

---

## 5. Measured Resource Footprint During Live Testing

| Container Name | Service Image | Port Mappings | Measured Memory RSS | Memory Limit | CPU % | Status |
|---|---|---|:---:|:---:|:---:|:---:|
| `central-bytebase` | `bytebase/bytebase:3.24.1` | `5678:8080` | 368.2 MiB | 3.723 GiB | 0.52% | Healthy |
| `central-infisical` | `infisical/infisical:v0.167.8` | `8083:8080` | 178.4 MiB | 3.723 GiB | 0.41% | Healthy |
| `central-supabase-db` | `supabase/postgres:15.1.1.78` | `5432:5432` | 185.1 MiB | 3.723 GiB | 0.05% | Healthy |
| `central-temporal` | `temporalio/temporal:1.10.0` | `7233:7233, 8233:8233` | 168.0 MiB | 3.723 GiB | 1.28% | Healthy |
| `central-apache-age` | `apache/age:release_PG16_1.6.0` | `5433:5432` | 94.8 MiB | 3.723 GiB | 0.00% | Healthy |
| `central-qdrant` | `qdrant/qdrant:v1.20.0` | `6333:6333, 6334:6334` | 57.2 MiB | 3.723 GiB | 1.45% | Healthy |
| `central-openfga` | `openfga/openfga:v1.22.1` | `8081:8080, 8082:8081` | 58.1 MiB | 3.723 GiB | 0.85% | Healthy |
| `central-valkey` | `valkey/valkey:8.0.2-alpine` | `6379:6379` | 6.5 MiB | 3.723 GiB | 0.12% | Healthy |
| **Total Active Stack** | **8 Running Containers** | — | **1,116.3 MiB** | **3.723 GiB** | — | **0 OOM Events** |

Host Windows RAM: 8.00 GB Total, ~820 MB Free physical headroom maintained throughout testing.
No swap thrashing or system instability occurred.
