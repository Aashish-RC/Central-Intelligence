# CENTRAL INTELLIGENCE V1 — LIVE INTEGRATION TEST RESULTS (STAGE S2)

**Author:** QA Engineering Lead & Infrastructure Verifier  
**Target:** Dedicated Live Integration Testing (Stage S2)  
**Date:** 2026-11-17  
**Working Revision:** `481d10dee0bf19ffa5a721b17a134b9d8d0fff46` (`481d10d`)  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Execution Environment:** Local Hybrid Staging (Windows 11 x64, WSL2 Engine, Docker 29.9.2, Python 3.12.12 venv)  
**Status:** **STAGE S2 ACTIVE — 4/11 GENUINE PASSES, 1 SIMULATED, 6 BLOCKED (CREDENTIALS/CODESPACE)**  

---

## 1. Executive Summary

In accordance with `docs/V1_TEST_EXECUTION_PLAN.md` and strict operating constraints:
- Zero paid spending incurred ($0.00).
- Complete enterprise stack was **NOT** launched simultaneously on the 8 GB host to prevent host OOM lockups.
- Services were brought up sequentially in isolated groups (Ring 0 Foundation & Ring 1 Identity) and monitored with live `docker stats`.
- Total active container RAM consumption remained bounded at **910 MiB** across 7 running services.
- Real services were tested; mocked/simulated tests are strictly distinguished from genuine live passes.

### Results Overview
- **Genuine Live Integration Passes:** **4 of 11** (OpenFGA, Temporal, PostgreSQL/pgvector, Sandbox Container Isolation).
- **Auxiliary Live Passes (Foundation):** **4 of 4** (Valkey Redis wire roundtrip, Qdrant vector store, Apache AGE graph adapter, Temporal basic echo).
- **Simulated (Mocked) Passes:** **1 of 11** (Kamal deployment sequence).
- **Blocked Scenarios:** **6 of 11** (Infisical, Lago, OpenMeter, SigNoz, Bytebase, LibreChat).
- **Failed Scenarios (Defects):** **0** (All runnable tests passed clean on first execution without regression).

---

## 2. The 11 Historical Live Integration Scenarios Matrix

| ID | Target Service | Service Version / Image | Exact Test Command | Credentials & Dependencies | Execution Evidence | Status | Defects Discovered & Remediation |
|---|---|---|---|---|---|:---:|---|
| **SC-01** | **OpenFGA** | `openfga/openfga:v1.22.1` (port 8081) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_openfga_persists_across_python_restart -v` | `OPENFGA_LIVE_URL="http://localhost:8081"` | Created store `e2e-fga-...`, authorization model v1.1 registered; written tuple `viewer` in process 1; permission checked in fresh process 2 (`OpenFGAAdapter`). Returned 0. | **✅ PASSED (GENUINE LIVE)** | None. Persistence verified across Python process boundaries. |
| **SC-02** | **Infisical** | `infisical/infisical:v0.167.8` | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_infisical_persists_across_python_restart -v` | `INFISICAL_LIVE_URL`, `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET` (Universal Auth) | Preflight fail-closed check triggered. Machine identity credentials and project workspace unprovisioned. | **🟡 BLOCKED** | Awaiting disposable staging machine credentials in GitHub Codespace. |
| **SC-03** | **Lago** | `lago-api:3000` (AGPL-3.0) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_lago_persists_across_python_restart -v` | `LAGO_LIVE_URL`, `LAGO_API_KEY`, Redis, Postgres | Full multi-tier Lago stack exceeds 8 GB host memory safe threshold. `LAGO_API_KEY` absent. | **🟡 BLOCKED** | Memory constraint on 8 GB laptop; requires 16 GB Codespace quarantine net. |
| **SC-04** | **OpenMeter** | `openmeter:8888` | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_openmeter_persists_across_python_restart -v` | `OPENMETER_LIVE_URL`, Apache Kafka, ClickHouse | ClickHouse + Kafka sink exceeds laptop RAM headroom; `OPENMETER_LIVE_URL` unconfigured. | **🟡 BLOCKED** | Requires 16 GB Codespace staging instance for ClickHouse/Kafka cluster. |
| **SC-05** | **SigNoz** | `signoz:3301` | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_signoz_persists_across_python_restart -v` | `SIGNOZ_LIVE_URL`, OTel Collector, ClickHouse cluster | SigNoz telemetry cluster requires ~4–8 GB RAM; prohibited on 8 GB host by zero-OOM constraint. | **🟡 BLOCKED** | Heavy enterprise stack deferred to 16 GB GitHub Codespace. |
| **SC-06** | **Temporal** | `temporalio/temporal:1.10.0` (port 7233) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_temporal_workflow_survives_worker_restart -v` | `TEMPORAL_LIVE_URL="localhost:7233"` | 5-node DAG workflow started (`CIDagWorkflow`). Worker 1 SIGKILL'd mid-execution. Worker 2 restarted, replayed workflow history from Temporal server, executed all 5 steps to completion. | **✅ PASSED (GENUINE LIVE)** | None. Server-side event replay and worker recovery verified. |
| **SC-07** | **PostgreSQL / pgvector** | `supabase/postgres:15.1.1.78` (port 5432) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_supabase_relational_and_vector_persist -v` | `POSTGRES_LIVE_URL="postgresql://postgres:postgres-development-pass@localhost:5432/postgres"` | Subprocess 1 inserted relational table/row and stored 3D vector embedding. Subprocess 2 queried row and performed pgvector cosine similarity search (`top_k=1`), retrieving exact matching document. | **✅ PASSED (GENUINE LIVE)** | None. Relational and vector durability verified across Python restarts. |
| **SC-08** | **Sandbox Isolation** | `python:3.12-slim` container on local Docker daemon | `pytest tests/integration/test_c3_sandbox_isolation_live.py -m live -v` & `test_sandbox_executes_real_python` | `SANDBOX_LIVE="1"`, Docker daemon | 12/12 C3 runtime isolation controls passed: real code computed (`print(2+2)` -> `4`), platform isolation verified (Linux container vs Windows host), read-only rootfs enforced, host mounts blocked, zero privilege escalation (`CapEff=0`), CPU & memory ceilings held. | **✅ PASSED (GENUINE LIVE)** | None. Container execution is completely unmocked and isolated. |
| **SC-09** | **Kamal Deployment** | N/A (Docker / Kamal CLI) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_kamal_deployment_command_sequence_is_simulated -v` | Kamal CLI, SSH target host (simulated in test) | Executed complete deploy phase sequence: `kamal lock acquire` -> `kamal registry push` -> `kamal app boot` -> `kamal proxy boot` -> `kamal app stop` -> `kamal lock release`. Phase marked COMPLETED. | **🟡 SIMULATED (Mocked)** | Test verifies command sequence and ordering via mocks; real server deployment deferred per constraint. |
| **SC-10** | **Bytebase** | `bytebase/bytebase:3.24.1` (port 5678) | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_bytebase_migration_executes_real_ddl -v` | `BYTEBASE_LIVE_URL="http://localhost:5678"`, `BYTEBASE_API_TOKEN` | Bytebase container online and responding HTTP 200 on `/healthz`. API calls return HTTP 401 (`access token not found`) because disposable workspace admin token is not provisioned. | **🟡 BLOCKED** | Awaiting disposable workspace setup / service token provisioning. |
| **SC-11** | **LibreChat to Gateway** | `librechat-dev` + reasoning gateway | `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_librechat_routes_to_reasoning_gateway -v` | `LIBRECHAT_LIVE_URL`, `REASONING_GATEWAY_URL`, MongoDB, MeiliSearch | LibreChat container and multi-tier dependencies (Mongo, MeiliSearch) not provisioned on 8 GB host. | **🟡 BLOCKED** | Staging multi-container footprint requires 16 GB Codespace environment. |

---

## 3. Auxiliary Live Stack Integrations (Foundation Ring)

In addition to the 11 historical scenarios, the core foundation and graph layers were verified live against real running containers:

| Service | Version / Port | Test Name | Execution Result |
|---|---|---|:---:|
| **Valkey** | `valkey:8.0.2-alpine` (port 6379) | `test_valkey_redis_wire_roundtrip_e2e` | **✅ PASSED (LIVE)** |
| **Qdrant** | `qdrant/qdrant:v1.20.0` (port 6333) | `test_qdrant_vector_roundtrip_e2e` | **✅ PASSED (LIVE)** |
| **Apache AGE** | `apache/age:release_PG16_1.6.0` (port 5433) | `test_postgres_apache_age_graph_adapters_e2e` | **✅ PASSED (LIVE)** |
| **Temporal Echo** | `temporal:1.10.0` (port 7233) | `test_temporal_workflow_execution_e2e` | **✅ PASSED (LIVE)** |

---

## 4. Measured Resource Footprint During Live Testing

| Container Name | Service Image | Port Mappings | Measured Memory RSS | Memory Limit | CPU % | Status |
|---|---|---|:---:|:---:|:---:|:---:|
| `central-bytebase` | `bytebase/bytebase:3.24.1` | `5678:8080` | 360.6 MiB | 3.723 GiB | 0.47% | Healthy |
| `central-supabase-db` | `supabase/postgres:15.1.1.78` | `5432:5432` | 171.3 MiB | 3.723 GiB | 0.03% | Healthy |
| `central-temporal` | `temporalio/temporal:1.10.0` | `7233:7233, 8233:8233` | 166.0 MiB | 3.723 GiB | 1.34% | Healthy |
| `central-apache-age` | `apache/age:release_PG16_1.6.0` | `5433:5432` | 94.2 MiB | 3.723 GiB | 0.00% | Healthy |
| `central-qdrant` | `qdrant/qdrant:v1.20.0` | `6333:6333, 6334:6334` | 56.4 MiB | 3.723 GiB | 1.55% | Healthy |
| `central-openfga` | `openfga/openfga:v1.22.1` | `8081:8080, 8082:8081` | 55.5 MiB | 3.723 GiB | 12.43% | Healthy |
| `central-valkey` | `valkey/valkey:8.0.2-alpine` | `6379:6379` | 6.3 MiB | 3.723 GiB | 4.31% | Healthy |
| **Total Active Stack** | **7 Running Containers** | — | **910.3 MiB** | **3.723 GiB** | — | **0 OOM Events** |

Host Windows RAM: 8.00 GB Total, ~1.1 GB Free physical headroom maintained throughout testing.
No swap thrashing or system instability occurred.
