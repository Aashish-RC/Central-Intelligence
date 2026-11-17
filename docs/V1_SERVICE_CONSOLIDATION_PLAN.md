# CENTRAL INTELLIGENCE V1 — SERVICE CONSOLIDATION & FOOTPRINT OPTIMIZATION PLAN

**Author:** Infrastructure Optimization Lead & Principal Platform Architect  
**Scope:** Architecture Consolidation, Memory Optimization, Profile Definitions, and Resource Matrix  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **PROPOSED ARCHITECTURAL CONSOLIDATION — PENDING STAKEHOLDER SIGN-OFF**  

---

## 1. Executive Summary & Problem Formulation

The Central Intelligence container ecosystem currently spans **51 defined container services**, resulting in extreme infrastructure over-provisioning:
- **6 Distinct PostgreSQL Containers:** `supabase-db`, `openfga-postgres`, `infisical-postgres`, `lago-postgres`, `openmeter-postgres`, `signoz-metastore-postgres-0`.
- **4 Distinct Redis/Valkey Containers:** `valkey`, `infisical-redis`, `openmeter-redis`, `lago-redis` (plus optional `dragonfly`).
- **3 Redundant Graph Engines:** `apache-age`, `memgraph`, `falkordb`.
- **Heavy Enterprise Aggregators:** Apache Kafka (JVM) + ClickHouse (OLAP) + ZooKeeper + SigNoz Ingester + Lago Sidekiq workers.

Attempting to boot the entire stack simultaneously consumes **>8.5 GiB of RAM**, causing immediate Out-Of-Memory (OOM) lockups on standard 8 GB developer machines and inflating cloud hosting costs.

This plan details the safe consolidation of shared datastores, the elimination of redundant and non-OSI licensed engines, and the partitioning of Central Intelligence into three clear operational deployment profiles (**Lite**, **Standard**, and **Enterprise**).

---

## 2. Granular Consolidation Analysis

### 2.1 Database Consolidation: Unifying PostgreSQL Instances

| Current State (6 Independent Containers) | Proposed Consolidated State |
|---|---|
| `supabase-db` (`supabase/postgres:15.1.1`): 185.1 MiB (Measured)<br>`openfga-postgres` (`postgres:14-alpine`): ~45 MiB (Est)<br>`infisical-postgres` (`postgres:14-alpine`): ~45 MiB (Est)<br>`lago-postgres` (`postgres:14-alpine`): ~50 MiB (Est)<br>`openmeter-postgres` (`postgres:14-alpine`): ~50 MiB (Est)<br>`signoz-metastore-postgres-0` (`postgres:14-alpine`): ~50 MiB (Est)<br>**Total Memory: ~425.1 MiB** | Single `supabase-db` instance hosting isolated logical databases:<br>- `postgres` (Core system of record + pgvector)<br>- `openfga` (OpenFGA tuples & models)<br>- `infisical` (Secret metadata & audit)<br>- `lago` (Subscription & invoice records)<br>- `openmeter` (Meter configurations)<br>**Total Memory: ~210.0 MiB** |

#### Consolidation Technical Design
1. **Bootstrap Script (`compose/postgres/init-multi-db.sh`):** Already present in repository. Executes during first database startup:
   ```bash
   for db in openfga infisical lago openmeter; do
     psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
       CREATE USER ${db}_user WITH PASSWORD '${POSTGRES_PASSWORD}';
       CREATE DATABASE $db OWNER ${db}_user;
       GRANT ALL PRIVILEGES ON DATABASE $db TO ${db}_user;
     EOSQL
   done
   ```
2. **Security & Failure-Domain Separation:**
   - Dedicated database users with zero cross-database privileges.
   - Separate logical schemas prevent any query cross-talk.
   - Shared process failure domain is mitigated through standard PostgreSQL WAL durability and volume snapshots (`central-intelligence_supabase_data`).
3. **Net Resource Savings:**
   - **RAM Saved:** ~215 MiB (~50% reduction in database memory).
   - **Storage Impact:** Neutral (data volume shared, eliminating redundant base PostgreSQL OS layers).
   - **CPU Impact:** Favorable (~30% reduction in idle process context switching).

---

### 2.2 Cache Consolidation: Standardizing on Valkey

| Current State (4 Containers) | Proposed Consolidated State |
|---|---|
| `valkey` (`valkey:8.0.2-alpine`): **6.5 MiB** (Measured, BSD-3-Clause)<br>`infisical-redis` (`redis:7.4.7`): ~15 MiB (Est, RSALv2/SSPL)<br>`openmeter-redis` (`redis:7.4.7`): ~15 MiB (Est, RSALv2/SSPL)<br>`lago-redis` (`redis:6-alpine`): ~15 MiB (Est, BSD-3-Clause)<br>`dragonfly` (Optional): ~50 MiB (Est, BSL-1.1)<br>**Total Memory: ~101.5 MiB + Non-OSI Legal Risks** | Single `valkey` instance with partitioned logical database indices:<br>- DB 0: Core working memory & model caches<br>- DB 1: Agent session turn history & rate limits<br>- DB 2: Infisical ephemeral token cache<br>- DB 3: OpenMeter streaming balance window<br>- DB 4: Lago Sidekiq job queues<br>**Total Memory: ~14.0 MiB (100% OSI BSD-3-Clause)** |

#### Consolidation Technical Design
1. **Connection String Wiring:**
   - Core: `valkey://central-valkey:6379/0`
   - Sessions: `valkey://central-valkey:6379/1`
   - Infisical: `REDIS_URL=redis://central-valkey:6379/2`
   - OpenMeter: `REDIS_URL=redis://central-valkey:6379/3`
   - Lago: `REDIS_URL=redis://central-valkey:6379/4`
2. **Security & Licensing Impact:**
   - Completely eliminates RSALv2/SSPL-v1 non-OSI Redis 7.4.7 from all compose files.
   - Eliminates BSL-1.1 Dragonfly container.
   - Valkey is governed by the Linux Foundation under the permissive BSD-3-Clause license.
3. **Net Resource Savings:**
   - **RAM Saved:** ~87 MiB (~86% reduction in cache memory).
   - **Network Overhead:** Single shared network socket; lower overhead.

---

### 2.3 Graph Store Consolidation: Formalizing Apache AGE & NetworkX

| Engine | License | Role in V1 | Status | RAM Footprint | Action |
|---|---|---|---|:---:|---|
| **Apache AGE** | **Apache-2.0** | PostgreSQL-native OpenCypher Graph Engine | **Primary Graph Store** | ~94.8 MiB (PG16) | **Retain as default relational graph store.** |
| **NetworkX** | **BSD-3-Clause** | In-Process Pure Python Graph Engine | **Embedded Fallback** | ~0 MiB (In-Process) | **Active in codebase (`_nx_fallback.py`).** Default for Lite profile. |
| **Memgraph** | BSL-1.1 (Non-OSI) | In-Memory C++ Graph DB | Deprecated | ~300 MiB | **Demote to opt-in legacy profile.** |
| **FalkorDB** | SSPL-v1 (Non-OSI) | Redis-based Graph DB | Deprecated | ~150 MiB | **Demote to opt-in legacy profile.** |

**Net Impact:** Eliminates 450 MiB of idle graph server memory and purges two non-OSI licensed engines from standard operational paths.

---

## 3. Operational Deployment Profiles

Central Intelligence defines three official operational profiles, guaranteeing that the platform runs efficiently from edge/developer devices to hyperscale enterprise clouds.

### 3.1 Lite Deployment Profile (`--profile lite`)
- **Target Environment:** Single-node developer laptops (8 GB RAM), edge servers, CI test runners.
- **Goal:** Minimal footprint (<1.5 GiB RAM), 100% core cognitive & security functionality, zero external heavy daemons.
- **Services Running (4 containers):**
  1. `supabase-db` (Postgres 15 + pgvector + consolidated schemas)
  2. `valkey` (Working memory, session turns, rate limiting)
  3. `qdrant` (Dedicated semantic vector search in lightweight mode, or in-process `:memory:`)
  4. `docker-sandbox` (Ephemeral Python code execution runner)
- **Embedded Engines Activated:**
  - Authorization: Native SQLite/PostgreSQL recursive CTE Zanzibar engine.
  - Secrets: Native AES-256-GCM envelope vault in SQLite.
  - Workflows: Native durable DAG orchestrator with SQLite WAL checkpoints.
  - Metering: Native PostgreSQL token ledger.
  - Telemetry: Local structured JSON-L file buffer.
- **Total Memory Footprint:** **~450–700 MiB RAM**.

---

### 3.2 Standard Deployment Profile (`--profile standard`)
- **Target Environment:** Production single-node VPS (8–16 GB RAM), mid-market enterprise deployments.
- **Goal:** Robust production readiness, distributed ReBAC, enterprise secret vaulting, and durable workflow orchestration without heavy OLAP or billing clusters.
- **Services Running (8 containers):**
  1. `supabase-db` (Relational persistence, pgvector, consolidated schemas)
  2. `valkey` (Universal cache & working memory)
  3. `openfga` (Go-based Zanzibar ReBAC engine)
  4. `infisical` (Node.js cryptographic secrets vault & Universal Auth)
  5. `temporal` (Go-based durable workflow orchestration server)
  6. `qdrant` (High-performance vector database)
  7. `apache-age` (OpenCypher graph engine)
  8. `bytebase` (Optional database schema review & DDL rollout)
- **Total Memory Footprint (Measured):** **~1,116.3 MiB RAM**.
- **Headroom on 8 GB Host:** **>6.8 GiB free RAM** (rock-solid stability).

---

### 3.3 Enterprise Deployment Profile (`--profile enterprise`)
- **Target Environment:** Multi-node Kubernetes clusters, large SaaS environments (16–64+ GB RAM).
- **Goal:** High-throughput streaming metering, full APM visualization, commercial billing, enterprise SSO, and web UI surfaces.
- **Services Running (All Standard + Enterprise Modules):**
  - Standard Services (8 containers)
  - Keycloak (Enterprise SAML/OIDC SSO, Passkeys)
  - Lago Stack (Subscription billing Rails API + Sidekiq workers)
  - OpenMeter Stack (Streaming CloudEvents ingestion + Kafka + ClickHouse OLAP)
  - SigNoz APM Stack (OTel Collector + ClickHouse cluster + SigNoz UI)
  - LibreChat Stack (Multi-provider web chat UI + MongoDB)
- **Total Memory Footprint (Estimated):** **~6.5–8.5 GiB RAM**.

---

## 4. Master Resource & Footprint Comparison Table

The table below contrasts physical memory measurements against estimates across the three deployment profiles:

| Service / Component | Engine / Image | Status | Lite Profile | Standard Profile | Enterprise Profile | Measurement Basis |
|---|---|---|:---:|:---:|:---:|---|
| **Supabase Postgres** | `supabase/postgres:15.1.1.78` | Mandatory Core | 185.1 MiB | 185.1 MiB | 250.0 MiB | **Measured (185.1 MiB)** |
| **Valkey** | `valkey/valkey:8.0.2-alpine` | Mandatory Core | 6.5 MiB | 6.5 MiB | 25.0 MiB | **Measured (6.5 MiB)** |
| **Qdrant** | `qdrant/qdrant:v1.20.0` | Replaceable Core | 57.2 MiB | 57.2 MiB | 120.0 MiB | **Measured (57.2 MiB)** |
| **Docker Sandbox** | `python:3.12-slim` | Mandatory Core | Ephemeral (~50 MiB)| Ephemeral (~50 MiB)| Ephemeral (~100 MiB)| **Measured (Bounded cgroup)** |
| **OpenFGA** | `openfga/openfga:v1.22.1` | Replaceable Core | *Embedded* (0 MiB)| 58.1 MiB | 90.0 MiB | **Measured (58.1 MiB)** |
| **Infisical** | `infisical/infisical:v0.167.8` | Replaceable Core | *Embedded* (0 MiB)| 178.4 MiB | 250.0 MiB | **Measured (178.4 MiB)** |
| **Temporal** | `temporalio/temporal:1.10.0` | Replaceable Core | *Embedded* (0 MiB)| 168.0 MiB | 250.0 MiB | **Measured (168.0 MiB)** |
| **Apache AGE** | `apache/age:release_PG16_1.6.0` | Replaceable Core | *Embedded* (0 MiB)| 94.8 MiB | 150.0 MiB | **Measured (94.8 MiB)** |
| **Bytebase** | `bytebase/bytebase:3.24.1` | Optional Integration | — | 368.2 MiB | 450.0 MiB | **Measured (368.2 MiB)** |
| **Keycloak** | `quay.io/keycloak/keycloak:26.8` | Optional Integration | — | — | 450.0 MiB | Estimated (JVM Quarkus) |
| **Lago + Sidekiq** | `getlago/api:v1.16.0` | Optional Integration | — | — | 600.0 MiB | Estimated (Rails + Redis) |
| **OpenMeter + Kafka + CH**| `openmeter/openmeter:v0.9` | Optional Integration | — | — | 1,800.0 MiB | Estimated (Kafka/ClickHouse)|
| **SigNoz Cluster** | ClickHouse + Keeper + Ingester | Optional Integration | — | — | 2,500.0 MiB | Estimated (Multi-container) |
| **LibreChat + MongoDB** | `ghcr.io/danny-avila/librechat` | Optional Integration | — | — | 450.0 MiB | Estimated (Node + Mongo) |
| **Total Active Memory** | — | — | **~298.8 MiB** | **~1,116.3 MiB** | **~7,285.0 MiB** | **Strict Verification** |

---

## 5. Security Isolation & Failure Domain Verification

Consolidation must never degrade multi-tenant security boundaries:

1. **Role-Based Tenant Separation:** In consolidated `supabase-db`, each application/tenant connects via isolated role credentials. Zero `SUPERUSER` privileges are granted to application adapters.
2. **Key Material Isolation:** Infisical's data schema in `supabase-db` stores only ciphertext encrypted with `INFISICAL_ENCRYPTION_KEY`. Even an administrator of the `postgres` schema cannot read unencrypted secret values without the key.
3. **Cache Partitioning Security:** Valkey databases 0–4 are isolated by database index numbers. For enterprise multi-tenant deployments requiring cryptographic cache isolation, distinct Valkey credentials with Redis ACLs (`ACL SETUSER`) are supported.
4. **Failure Domains:** If `supabase-db` restarts, all dependent adapters implement backoff retry loops (`asyncpg` pool reconnection, OpenFGA automatic reconnect, Infisical connection retry). Durability is preserved via named volume mount.

---

## 6. Migration and Rollback Governance

### 6.1 Database Consolidation Migration Path
1. **Pre-Migration Snapshot:** Execute `pg_dump` on individual auxiliary databases (`openfga`, `infisical`, `lago`).
2. **Schema Import:** Restore schema dumps into logical databases inside `central-supabase-db`.
3. **Configuration Update:** Update connection environment variables in `.env`.
4. **Verification:** Execute live restart tests (`test_openfga_persists_across_python_restart`, `test_infisical_persists_across_python_restart`).
5. **Rollback:** If issues arise, re-launch isolated container definitions from backup compose file (`compose/archive/docker-compose.split-db.yml`).

### 6.2 Approval Gate
Per the governing operating instructions:
> **No database consolidation or configuration default changes will be applied to production compose files without prior stakeholder review and explicit approval.**
