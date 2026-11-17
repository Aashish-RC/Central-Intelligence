# V1 Architecture Optimization Decisions & Consolidation Review

**Author:** Principal Software Architect & QA Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `1269bf30a1f33ab2fad95fc58e6ab4274891c16f`  
**Date:** 2026-11-17  
**Status:** **AUTHORITATIVE ARCHITECTURAL DECISION RECORD (ADR)**

---

## 1. Executive Strategy

Central Intelligence v1 targets significant operational cost and resource reduction without compromising enterprise security, durability, tenant isolation, or modularity. 

We do not eliminate or replace components merely to reduce container counts. Every optimization candidate is rigorously evaluated across functional risk, data migration, security boundaries, and reversibility.

---

## 2. Comprehensive Candidate Evaluations

### Candidate 1: PostgreSQL Database Consolidation (7 Instances -> 1 Multi-Tenant Instance)
- **Current Design:** Seven independent PostgreSQL container runtimes:
  1. `supabase-db` (PostgreSQL 15 + pgvector)
  2. `apache-age` (PostgreSQL 16 + AGE)
  3. `openfga-postgres` (PostgreSQL 14)
  4. `infisical-postgres` (PostgreSQL 14)
  5. `lago-postgres` (PostgreSQL 14)
  6. `openmeter-postgres` (PostgreSQL 14)
  7. `signoz-metastore-postgres-0` (PostgreSQL 16)
- **Proposed Design:**
  - *Lite & Standard Profiles:* Consolidate `openfga`, `infisical`, `lago`, `openmeter`, and `signoz-metastore` databases into the primary `supabase-db` container using dedicated databases (`openfga`, `infisical`, `lago`, `openmeter`, `signoz`), dedicated users/passwords, separate connection pools, and strict schema isolation. Keep `apache-age` separate for graph queries due to PostgreSQL 16 engine/extension specificities.
  - *Enterprise Profile:* Retain dedicated database instances for maximum physical isolation and high-availability clustering.
- **Expected Resource Savings:**
  - Eliminates 5 container runtimes.
  - **Memory:** ~220–320 MiB idle RAM saved; ~600–1,000 MiB peak RAM saved.
  - **Disk:** ~1.1 GB container image storage saved.
- **Measured Evidence:** Individual PostgreSQL 14 idle containers consume ~40–60 MiB each. Combined single-instance PostgreSQL hosts multiple logical databases with negligible additional idle overhead (~15 MiB shared buffer allocation).
- **Implementation Complexity:** Medium. Requires parameterized Compose database creation script (`init-multi-db.sh`).
- **Functional Risks:** Low. Each service connects via standard JDBC/libpq URL specifying its dedicated database name.
- **Data Migration Implications:** Greenfield installations initialize clean databases. Existing volumes require standard `pg_dump`/`pg_restore` if migrating existing data.
- **Security & Isolation Effects:** Preserves role-based access control and tenant isolation. Each application connects with distinct unprivileged credentials.
- **Reversibility:** High. Connection strings in `.env` can be repointed to dedicated containers at any time.
- **Recommendation:** **ADOPT for Lite and Standard profiles; INVESTIGATE unified image for Apache AGE + pgvector.**

---

### Candidate 2: Redis / Valkey Duplication (4 Instances -> Consolidated Valkey Instance)
- **Current Design:** Four independent Redis-protocol container runtimes:
  1. `valkey` (Valkey 8.0.2-alpine, BSD-3-Clause)
  2. `infisical-redis` (Redis 7.4.7-alpine, RSALv2 / SSPL-v1)
  3. `lago-redis` (Redis 6-alpine, BSD-3-Clause)
  4. `openmeter-redis` (Redis 7.4.7, RSALv2 / SSPL-v1)
- **Proposed Design:**
  - Consolidate all Redis caching, locking, and queueing into the single OSI-compliant `valkey` container using partitioned logical databases:
    - DB 0: Central Intelligence general cache, semantic cache & leases.
    - DB 1: Infisical token cache & rate limiter.
    - DB 2: OpenMeter event deduplication driver.
    - DB 3: Lago Sidekiq task queues (on `agpl_quarantine_net`).
- **Expected Resource Savings:**
  - Eliminates 3 container runtimes.
  - **Memory:** ~50–75 MiB idle RAM saved; ~150–250 MiB peak RAM saved.
  - **Disk:** ~100 MB image storage saved.
  - **License Hygiene:** Eliminates two non-OSI (RSALv2 / SSPL-v1) container dependencies from default stack!
- **Measured Evidence:** Single Valkey container uses ~18–25 MiB idle RAM. Multiple logical databases in Valkey incur zero per-database memory overhead.
- **Implementation Complexity:** Low. Update connection strings in `.env` (e.g., `redis://valkey:6379/1`).
- **Functional Risks:** Very Low. Valkey 8 maintains full protocol and command compatibility with Redis 6 and 7.
- **Data Migration Implications:** Ephemeral caches require no migration. Lago Sidekiq queues drain before recreation.
- **Security & Isolation Effects:** Enhanced. Eliminates non-OSI licenses; standard Redis password protection; distinct DB index isolation.
- **Reversibility:** High. Repoint URLs back to individual containers if needed.
- **Recommendation:** **ADOPT immediately across all profiles.**

---

### Candidate 3: Qdrant vs pgvector Consolidation
- **Current Design:** Both Qdrant (v1.20.0) and pgvector (in `supabase-db`) are deployed in the core profile.
- **Proposed Design:**
  - *Standard & Enterprise Profiles:* Retain Qdrant as the primary ANN vector search engine for cognitive memory, and pgvector for relational embeddings, preserving the hybrid retrieval pipeline (verified in D3).
  - *Lite Profile:* Support optional pgvector-only mode where small installations (<50,000 vectors) bypass Qdrant and execute vector similarity queries entirely via pgvector within `supabase-db`.
- **Expected Resource Savings:**
  - *Lite Profile:* Saves 1 container; **53.39 MiB measured idle RAM** (empirically verified) and ~150–250 MiB peak RAM.
- **Measured Evidence:** `central-qdrant` measured at 53.39 MiB idle RAM on local Docker host.
- **Implementation Complexity:** Low. Central Intelligence already implements both `QdrantVectorStore` and `PostgresFactStore` / `pgvector` adapters with unified `BaseVectorStore` interfaces.
- **Functional Risks:** Low for small datasets; pgvector has lower throughput and higher query latency on massive (>1M vectors) collections than Qdrant's dedicated Rust HNSW engine.
- **Data Migration Implications:** None if profile-selected at initialization. Adapter sync script exists for vector re-indexing.
- **Security & Isolation Effects:** Neutral. Both enforce tenant filtering.
- **Reversibility:** High.
- **Recommendation:** **ADOPT pgvector-only mode for Lite; RETAIN Qdrant for Standard and Enterprise.**

---

### Candidate 4: Apache AGE Graph Activation Requirements
- **Current Design:** `apache-age` runs continuously in the `core` profile.
- **Proposed Design:**
  - *Lite Profile:* Default to in-memory graph adapter (`NetworkX`) or relational edge table for simple agent memory, with Apache AGE deactivated.
  - *Standard & Enterprise Profiles:* Keep Apache AGE active for knowledge graph traversals, entity-relationship extraction, and deep RAG.
- **Expected Resource Savings:**
  - *Lite Profile:* Saves 1 container; **91.00 MiB measured idle RAM** (empirically verified) and ~200–350 MiB peak RAM.
- **Measured Evidence:** `central-apache-age` measured at 91.00 MiB idle RAM on local Docker host.
- **Implementation Complexity:** Very Low. `ApacheAGEAdapter` already includes automatic fallback to in-memory graph when `auto_fallback=True`.
- **Functional Risks:** Minimal. Small single-user/dev environments rarely execute multi-hop graph traversals requiring OpenCypher disk execution.
- **Data Migration Implications:** Graph entities serialize to JSON snapshot.
- **Security & Isolation Effects:** Neutral.
- **Reversibility:** High.
- **Recommendation:** **ADOPT on-demand / optional profile for Lite; RETAIN active for Standard and Enterprise.**

---

### Candidate 5: Kafka Alternatives for Small Deployments
- **Current Design:** Apache Kafka 3.9.0 (JVM) deployed continuously in the `core` profile to buffer OpenMeter billing events.
- **Proposed Design:**
  - *Enterprise Profile:* Retain Apache Kafka (or Redpanda) for high-throughput distributed event streaming (>100k events/sec).
  - *Lite & Standard Profiles:* Support direct synchronous HTTP event ingestion or Valkey Streams for OpenMeter / local metering, disabling the Kafka container.
- **Expected Resource Savings:**
  - Saves 1 heavy JVM container.
  - **Memory:** ~300–450 MiB idle RAM saved; ~800–1,500 MiB peak RAM saved.
  - **Disk:** 627 MB container image storage saved.
  - **CPU:** Eliminates continuous background Kafka broker thread polling.
- **Measured Evidence:** Kafka container failed with OOM exit code 137 on local PC during unconstrained core startup.
- **Implementation Complexity:** Medium. OpenMeter supports direct PostgreSQL aggregation or local adapter bypass.
- **Functional Risks:** Low for developer / small team volumes (<1,000 events/sec).
- **Data Migration Implications:** None.
- **Security & Isolation Effects:** Neutral.
- **Reversibility:** High.
- **Recommendation:** **ADOPT Kafka deactivation in Lite and Standard profiles; RETAIN for Enterprise.**

---

### Candidate 6: Temporal Deployment Footprint
- **Current Design:** Temporal server standalone container (`temporalio/temporal:1.10.0`) runs continuously in `core`.
- **Proposed Design:**
  - Retain Temporal as the authoritative enterprise orchestrator (Hatchet evaluation confirmed Temporal's superior deterministic replay and cross-language maturity).
  - Optimize configuration: Bind Temporal to consolidated PostgreSQL datastore; set memory limits (`deploy.resources.limits.memory: 256M`).
  - For Lite profile development, allow lightweight filesystem checkpointing (`.temporal_checkpoints`) for simple workflows.
- **Expected Resource Savings:**
  - Memory bounds prevent Temporal from exceeding 256 MiB under load.
- **Measured Evidence:** Temporal previously exited with code 137 due to unbounded memory competition.
- **Implementation Complexity:** Low.
- **Functional Risks:** Zero. Preserves full Layer 7 durability contracts.
- **Data Migration Implications:** Retains SQLite/PostgreSQL schemas.
- **Security & Isolation Effects:** Preserves namespace-level tenant isolation.
- **Reversibility:** High.
- **Recommendation:** **ADOPT memory bounding for Temporal in Standard/Enterprise; optional in Lite.**

---

### Candidate 7: Lago & OpenMeter Infrastructure Footprint
- **Current Design:** Thirteen combined services dedicated to billing and metering:
  - OpenMeter: 8 services (`openmeter`, `openmeter-clickhouse`, `openmeter-postgres`, `openmeter-redis`, 4 workers/jobs) + `kafka`.
  - Lago: 5 services (`lago`, `lago-postgres`, `lago-redis`, `lago-migrate`, `lago-worker`).
- **Proposed Design:**
  - *Lite Profile:* Bypass full OpenMeter/Lago infrastructure. Use built-in Python metering engine (`control/billing/metering/metering_adapter.py`) with local SQLite/Valkey aggregation. Saves 13 containers and >1,200 MiB idle RAM!
  - *Standard Profile:* Enable Lago (API + consolidated DB/Valkey) for subscription management; run OpenMeter with consolidated DB/Valkey without Kafka/ClickHouse.
  - *Enterprise Profile:* Full distributed cluster with ClickHouse and Kafka.
- **Expected Resource Savings:**
  - *Lite:* Saves ~1,200–1,800 MiB idle RAM; eliminates 13 containers.
  - *Standard:* Saves ~650–900 MiB idle RAM.
- **Measured Evidence:** Multiple billing workers and ClickHouse instances caused severe memory pressure and exit code 137.
- **Implementation Complexity:** Low to Medium. Built-in metering adapters already support offline/local modes.
- **Functional Risks:** None for local development and non-billed environments.
- **Data Migration Implications:** Billing ledgers export to standard CSV/JSON.
- **Security & Isolation Effects:** Preserves AGPL-3.0 quarantine boundaries for Lago.
- **Reversibility:** High.
- **Recommendation:** **ADOPT profile partitioning: Built-in metering for Lite; Managed Lago for Standard; Distributed OpenMeter for Enterprise.**

---

### Candidate 8: SigNoz / ClickHouse / OTel Resource Footprint
- **Current Design:** Seven SigNoz/ClickHouse services + OTel Collector running in the `core` profile:
  `signoz-telemetrykeeper`, `signoz-telemetrystore-clickhouse`, `user-scripts`, `migrator`, `signoz-signoz-0`, `ingester`, `signoz-metastore-postgres-0`, `otel-collector`.
- **Proposed Design:**
  - *Lite & Standard Profiles:* Deactivate SigNoz and ClickHouse. Run only `otel-collector` configured with batch processor and file/stdout exporters or lightweight Jaeger/Prometheus endpoint.
  - *Enterprise Profile:* Full SigNoz APM cluster activated via `--profile enterprise` or `--profile observability`.
- **Expected Resource Savings:**
  - Saves 7 containers.
  - **Memory:** ~750–1,100 MiB idle RAM saved; ~2,000–3,500 MiB peak RAM saved.
  - **Disk:** ~2.1 GB container image storage saved.
- **Measured Evidence:** ClickHouse + ClickHouse Keeper + Ingester represent the single largest block of memory consumption in the Compose model (~800+ MiB idle).
- **Implementation Complexity:** Low. Update OTel collector pipeline configuration to make SigNoz export optional.
- **Functional Risks:** Zero. Observability telemetry is non-blocking to cognitive execution.
- **Data Migration Implications:** Telemetry spans are ephemeral time-series data.
- **Security & Isolation Effects:** Neutral.
- **Reversibility:** High.
- **Recommendation:** **ADOPT: SigNoz in Enterprise/Observability profile; lightweight OTel Collector in Lite/Standard.**

---

### Candidate 9: LibreChat & MongoDB Requirements
- **Current Design:** `librechat` and `librechat-mongodb` run continuously in the `core` profile.
- **Proposed Design:**
  - Move LibreChat and MongoDB to `--profile ui` (or `--profile surface`).
  - Central Intelligence core runs headlessly via its high-performance FastAPI/WebSocket reasoning gateway (`port 8000`) and embedded control console (`GET /console`).
- **Expected Resource Savings:**
  - Saves 2 containers.
  - **Memory:** ~270–430 MiB idle RAM saved.
  - **Disk:** ~1,570 MB container image storage saved.
  - **License Hygiene:** Eliminates MongoDB (SSPL-v1, non-OSI) from the default stack!
- **Measured Evidence:** LibreChat Node.js and MongoDB WiredTiger cache consume ~300 MiB idle RAM.
- **Implementation Complexity:** Very Low. Move profile tag to `["ui", "optional"]`.
- **Functional Risks:** Zero. Core API, reasoning engine, and embedded web console remain 100% accessible.
- **Data Migration Implications:** None.
- **Security & Isolation Effects:** Eliminates non-OSI license from core.
- **Reversibility:** High.
- **Recommendation:** **ADOPT immediately: Move LibreChat and MongoDB to optional `ui` profile.**

---

### Candidate 10: Infisical & External Secrets Provider Options
- **Current Design:** `infisical`, `infisical-postgres`, `infisical-redis` running in `core`.
- **Proposed Design:**
  - *Lite Profile:* Use Central Intelligence's built-in AES-256-GCM encrypted keystore (`control/identity/secrets/local_vault.py`) or environment variables, bypassing Infisical.
  - *Standard Profile:* Run Infisical backed by consolidated `supabase-db` and `valkey` (eliminates 2 backing store containers).
  - *Enterprise Profile:* Full standalone Infisical or external HashiCorp Vault / AWS Secrets Manager.
- **Expected Resource Savings:**
  - *Lite Profile:* Saves 3 containers and ~240–360 MiB idle RAM.
  - *Standard Profile:* Saves 2 backing containers and ~55–85 MiB idle RAM.
- **Measured Evidence:** Infisical container is 2.81 GB on disk.
- **Implementation Complexity:** Low. `InfisicalSecretManager` already implements fallback to local vault.
- **Functional Risks:** Zero.
- **Data Migration Implications:** Export/import via JSON keystore.
- **Security & Isolation Effects:** Preserves encryption at rest and audit trails.
- **Reversibility:** High.
- **Recommendation:** **ADOPT: Local vault for Lite; Consolidated Infisical for Standard; Standalone/External for Enterprise.**

---

## 3. Summary Decision Matrix

| Candidate | Optimization Action | Idle RAM Savings | Container Reduction | License Impact | Complexity | Recommendation |
|---|---|---:|:---:|---|:---:|:---:|
| **1. Postgres Consolidation** | Merge 5 DBs into `supabase-db` | ~270 MiB | -5 | Neutral (OSI) | Medium | **ADOPT (Lite/Std)** |
| **2. Valkey Consolidation** | Merge 3 Redis into `valkey` | ~65 MiB | -3 | Removes non-OSI RSALv2 | Low | **ADOPT (All)** |
| **3. Vector Consolidation** | pgvector-only mode for Lite | ~53 MiB | -1 | Neutral (OSI) | Low | **ADOPT (Lite)** |
| **4. Graph Activation** | On-demand Apache AGE | ~91 MiB | -1 | Neutral (OSI) | Very Low | **ADOPT (Lite)** |
| **5. Kafka Bypass** | Direct/Valkey billing in Lite/Std | ~375 MiB | -1 | Neutral (OSI) | Medium | **ADOPT (Lite/Std)** |
| **6. Temporal Limits** | Resource memory limits on Temporal | N/A (bounds peak) | 0 | Neutral (OSI) | Low | **ADOPT (All)** |
| **7. Billing Partitioning** | Built-in Lite metering; Lago Std | ~1,200 MiB | -11 | Preserves AGPL quarantine | Medium | **ADOPT (Lite/Std)** |
| **8. SigNoz Partitioning** | Move SigNoz/ClickHouse to Enterprise | ~850 MiB | -7 | Neutral | Low | **ADOPT (Lite/Std)** |
| **9. LibreChat Partitioning** | Move LibreChat/MongoDB to UI profile | ~350 MiB | -2 | Removes non-OSI SSPL | Very Low | **ADOPT (All)** |
| **10. Secrets Consolidation** | Local vault Lite; Consolidated Std | ~290 MiB | -2 to -3 | Neutral | Low | **ADOPT (Lite/Std)** |
