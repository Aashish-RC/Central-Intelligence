# V1 Resource Baseline & Service Inventory

**Author:** Principal Software Architect & Infrastructure Optimization Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `1269bf30a1f33ab2fad95fc58e6ab4274891c16f`  
**Date:** 2026-11-17  
**Status:** **ACTIVE BASELINE — Complete 51-Service Inventory & Empirical Resource Audit**

---

## 1. Operating Environments & Physical Hardware Constraints

Central Intelligence v1 must run safely and cost-effectively within two primary development, verification, and early-stage operating tiers. Zero mandatory paid infrastructure is permitted.

### 1.1 Local Windows Development PC
- **CPU:** Intel Core i5-1035G1, 4 physical cores / 8 logical threads, 1.00 GHz base frequency (Ice Lake, 10nm).
- **Host RAM:** 8.00 GB total physical DDR4 RAM.
- **Observed Free Host RAM:** ~0.86 GiB during active developer sessions (background Windows OS, IDE, shells).
- **Docker Desktop Subsystem:** WSL2 Linux Kernel 5.15+ (cgroups v2).
- **Docker Daemon Memory Ceiling:** `3,997,401,088 bytes` (~3.72 GiB limit allocated in `.wslconfig`).
- **Disk Storage:** Ample local SSD storage.
- **Operating Rule:** Primary host for source development, static analysis, unit tests, fast mocked suites, and lightweight runtime subsets. **Starting all 37 core services simultaneously on this PC causes immediate cgroup memory exhaustion and kernel termination with Exit Code 137 (OOM Killer).**

### 1.2 GitHub Codespaces
- **Compute:** 4 vCPUs.
- **RAM:** 16.0 GB total system RAM.
- **Storage:** 32.0 GB ephemeral virtual disk.
- **Operating Rule:** Reserved for controlled integration batches, container build operations, and multi-service E2E verification where authorized. Never exceed storage bounds; clean intermediate build cache.

### 1.3 Financial & Governance Guardrails
- **Zero Mandatory Paid Infrastructure:** No licensed proprietary software, paid SaaS, or cloud compute that incurs charges.
- **Zero Paid API Invocations Without Explicit Approval:** External LLM reasoning, paid sandbox runners, and hosted third-party endpoints must remain mock-gated or disabled in automated test runs.
- **Data Protection:** Existing user-owned containers (`cool_hamilton`, running `central-qdrant`, `central-apache-age`), pre-existing databases, and named volumes must never be mutated or dropped without explicit consent.
- **Zero Unauthorized Commits/Pushes:** Strictly enforce review before remote mutation.

---

## 2. Empirical Verification & Historical Execution Baseline

### 2.1 Live Container Runtime Status (Local Docker Host)
Audited via `docker ps -a` and `docker stats --no-stream` on 2026-11-17:

| Container Name | Image | Status | Measured Idle RAM | Measured Peak RAM | Measured CPU | Port Bindings |
|---|---|---|---:|---:|---:|---|
| `central-qdrant` | `qdrant/qdrant:v1.20.0` | Up (healthy) | **53.39 MiB** | **NOT MEASURED** | 0.96% | 6333, 6334 |
| `central-apache-age` | `apache/age:release_PG16_1.6.0` | Up (healthy) | **91.00 MiB** | **NOT MEASURED** | 0.01% | 5433:5432 |
| `central-kafka` | `apache/kafka:3.9.0` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-bytebase` | `bytebase/bytebase:3.24.1` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-openfga` | `openfga/openfga:v1.22.1` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-keycloak` | `quay.io/keycloak/keycloak:26.8.2` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-temporal` | `temporalio/temporal:1.10.0` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-supabase-db` | `supabase/postgres:15.1.1.78` | Exited (137) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `central-valkey` | `valkey/valkey:8.0.2-alpine` | Exited (0) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |
| `ci-pgvector-test` | `pgvector/pgvector:pg16` | Exited (0) | **NOT MEASURED** | **NOT MEASURED** | **NOT MEASURED** | None |

> [!CAUTION]
> **Empirical Root Cause of Container Failures:** The containers `central-kafka`, `central-bytebase`, `central-openfga`, `central-keycloak`, `central-temporal`, and `central-supabase-db` all exited with **code 137 (SIGKILL / OOM)** because the existing `docker-compose.yml` specified no container memory ceilings (`deploy.resources.limits.memory`). When launched concurrently on the 3.72 GiB WSL2 Docker daemon, competing JVM (Keycloak, Kafka), Go (Temporal, OpenFGA), and C (PostgreSQL) allocators starved the cgroup memory pool.

### 2.2 Local Docker Image Sizes
Audited from local image store (`docker images`):

| Image Name / Repository | Tag | Local Disk Usage | Image Content Size | Licensing Type |
|---|---|---:|---:|---|
| `infisical/infisical` | `v0.167.8` | 2,810 MB | 612 MB | MIT (OSI) |
| `supabase/postgres` | `15.1.1.78` | 1,670 MB | 416 MB | Apache-2.0 / PostgreSQL |
| `quay.io/keycloak/keycloak` | `26.8.2` | 750 MB | 265 MB | Apache-2.0 (OSI) |
| `apache/age` | `release_PG16_1.6.0` | 684 MB | 180 MB | Apache-2.0 (OSI) |
| `pgvector/pgvector` | `pg16` | 647 MB | 162 MB | PostgreSQL (OSI) |
| `apache/kafka` | `3.9.0` | 627 MB | 218 MB | Apache-2.0 (OSI) |
| `bytebase/bytebase` | `3.24.1` | 511 MB | 128 MB | Apache-2.0 (OSI) |
| `qdrant/qdrant` | `v1.20.0` | 281 MB | 76.9 MB | Apache-2.0 (OSI) |
| `temporalio/temporal` | `1.10.0` | 180 MB | 42.8 MB | MIT (OSI) |
| `openfga/openfga` | `v1.22.1` | 114 MB | 27.7 MB | Apache-2.0 (OSI) |
| `valkey/valkey` | `8.0.2-alpine` | 57.6 MB | 16.3 MB | BSD-3-Clause (OSI) |
| `alpine` | `3.20` | 12.2 MB | 3.71 MB | MIT |

---

## 3. Complete 51-Service Inventory (Core & Optional Profiles)

Central Intelligence defines **37 services in the `core` profile** and **14 services in the `optional` profile** across `docker-compose.yml` and `compose/signoz/pours/deployment/compose.yaml`.

### 3.1 Core Profile Services (37 Services)

#### 1. `qdrant`
- **Purpose:** Primary vector database for cognitive long-term memory, semantic embeddings, and vector similarity search.
- **Layers & Capabilities:** Layer 2 (Memory Hierarchy), Layer 3 (Knowledge & Retrieval).
- **Mandatory / Optional:** Mandatory for hybrid retrieval.
- **Continuous / On-Demand:** Continuous (holds indexed vector collections).
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `qdrant_data` mounted at `/qdrant/storage`.
- **Image Size:** 281 MB on disk (76.9 MB content).
- **Measured Idle RAM:** **53.39 MiB** (empirically measured).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** 0.96% (empirically measured).
- **Disk/Volume:** `qdrant_data`.
- **Startup Time:** ~1.8s.
- **Availability & Recovery:** High availability; handles SIGTERM gracefully and replays WAL.
- **Consolidation / Sharing:** Can be consolidated into pgvector for minimal Lite profiles if HNSW approximate search performance is acceptable for small tenant workloads.
- **Security & Isolation:** Collection-level isolation with tenant ID payload filters.
- **License:** Apache-2.0 (OSI).

#### 2. `valkey`
- **Purpose:** In-memory key-value cache, semantic query caching, distributed locking, and fast ephemeral state.
- **Layers & Capabilities:** Layer 2 (Working Memory), Layer 4 (Reasoning Semantic Cache), Layer 8 (Task Leases), Layer 14 (Rate Limiting).
- **Mandatory / Optional:** Mandatory for distributed coordination and rate limiting.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `valkey_data` mounted at `/data`.
- **Image Size:** 57.6 MB on disk (16.3 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~18–25 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `valkey_data`.
- **Startup Time:** ~0.6s.
- **Availability & Recovery:** Fast in-memory restart; RDB/AOF persistence.
- **Consolidation / Sharing:** Single Valkey instance can replace the 4 isolated Redis containers (`infisical-redis`, `lago-redis`, `openmeter-redis`) using namespaced DB indices or key prefixes.
- **Security & Isolation:** TLS, password authentication, key prefixing.
- **License:** BSD-3-Clause (OSI).

#### 3. `supabase-db`
- **Purpose:** Primary enterprise relational persistence and pgvector embedding storage.
- **Layers & Capabilities:** Layer 2 (Fact Store), Layer 3 (Knowledge metadata), Layer 11 (Tenancy & Workspaces), Layer 12 (Identity/Credentials).
- **Mandatory / Optional:** Mandatory core relational store.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `supabase_db_data` mounted at `/var/lib/postgresql/data`.
- **Image Size:** 1,670 MB on disk (416 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~120–180 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `supabase_db_data`.
- **Startup Time:** ~4.5s.
- **Availability & Recovery:** ACID transactional guarantees, WAL crash recovery.
- **Consolidation / Sharing:** Primary database anchor. Can host databases/schemas for OpenFGA, Infisical, Lago, and Bytebase to eliminate 5 redundant PostgreSQL container runtimes.
- **Security & Isolation:** Role-based access control, schema separation, row-level security (RLS).
- **License:** Apache-2.0 / PostgreSQL.

#### 4. `apache-age`
- **Purpose:** Graph database extension on PostgreSQL 16 for knowledge graph entity-relationship traversal (openCypher queries).
- **Layers & Capabilities:** Layer 2 (Graph Memory Tier), Layer 3 (Knowledge Graph RAG).
- **Mandatory / Optional:** Mandatory for graph-based hybrid retrieval.
- **Continuous / On-Demand:** Continuous in Standard/Enterprise; on-demand in Lite.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `apache_age_data` mounted at `/var/lib/postgresql/data`.
- **Image Size:** 684 MB on disk (180 MB content).
- **Measured Idle RAM:** **91.00 MiB** (empirically measured).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** 0.01% (empirically measured).
- **Disk/Volume:** `apache_age_data`.
- **Startup Time:** ~3.2s.
- **Availability & Recovery:** Relational PostgreSQL WAL durability.
- **Consolidation / Sharing:** Can be compiled or enabled as an extension in the main PostgreSQL engine or loaded on demand.
- **Security & Isolation:** Graph-level and tenant-level labeling.
- **License:** Apache-2.0 (OSI).

#### 5. `temporal`
- **Purpose:** Durable workflow orchestration, state machine checkpointing, retry execution, and long-running agent workflows.
- **Layers & Capabilities:** Layer 7 (Durable Execution), Layer 8 (Multi-Agent Fleet Coordination).
- **Mandatory / Optional:** Mandatory for durable, pause-and-resume enterprise workflows.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** In-memory or database backing store.
- **Persistence Requirements:** Named volume `temporal_data` mounted at `/etc/temporal`.
- **Image Size:** 180 MB on disk (42.8 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~80–120 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `temporal_data`.
- **Startup Time:** ~3.5s.
- **Availability & Recovery:** Event sourcing architecture with deterministic replay.
- **Consolidation / Sharing:** Hatchet evaluated; Temporal remains pinned for enterprise v1 durability. Can use SQLite or shared PostgreSQL for metadata.
- **Security & Isolation:** Namespace-level isolation per tenant.
- **License:** MIT (OSI).

#### 6. `keycloak`
- **Purpose:** Centralized Identity and Access Management (IAM), OAuth2/OIDC provider, SSO, and user directory.
- **Layers & Capabilities:** Layer 11 (Multi-Tenancy), Layer 12 (Identity & Auth).
- **Mandatory / Optional:** Mandatory for enterprise SSO; optional in developer local setups with API-key authentication.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** Relational database (`supabase-db` or embedded dev database).
- **Persistence Requirements:** Named volume `keycloak_data`.
- **Image Size:** 750 MB on disk (265 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~350–550 MiB, JVM runtime).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `keycloak_data`.
- **Startup Time:** ~12–18s (JVM Quarkus boot).
- **Availability & Recovery:** Stateful session recovery from backing store.
- **Consolidation / Sharing:** In Lite profiles, internal JWT / API key governor can satisfy auth without starting heavy Keycloak JVM.
- **Security & Isolation:** Realm-level isolation, encrypted credentials.
- **License:** Apache-2.0 (OSI).

#### 7. `openfga-postgres`
- **Purpose:** Dedicated PostgreSQL 14 backing datastore for OpenFGA relationship tuples.
- **Layers & Capabilities:** Layer 12 (ReBAC Authorization).
- **Mandatory / Optional:** Mandatory when OpenFGA runs with persistent storage.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `openfga_postgres_data`.
- **Image Size:** ~210 MB (registry content ~45 MB).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–60 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `openfga_postgres_data`.
- **Startup Time:** ~2.5s.
- **Availability & Recovery:** Relational persistence.
- **Consolidation / Sharing:** Prime candidate to merge into `supabase-db` as a dedicated database `openfga` or schema `openfga`.
- **Security & Isolation:** Isolated database user and credentials.
- **License:** PostgreSQL (OSI).

#### 8. `openfga-migrate`
- **Purpose:** Database migration job applying OpenFGA relational schema updates.
- **Layers & Capabilities:** Layer 12 (ReBAC Authorization).
- **Mandatory / Optional:** Transient one-shot migration job.
- **Continuous / On-Demand:** Runs once at startup (`restart: on-failure`).
- **Startup Dependencies:** `openfga-postgres` (condition: `service_healthy`).
- **Persistence Requirements:** Ephemeral.
- **Image Size:** 114 MB on disk.
- **Measured Idle RAM:** **NOT MEASURED** (Exits immediately upon completion).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.2s.
- **Availability & Recovery:** Exit 0 on success.
- **Consolidation / Sharing:** Runs in-process or via CLI script during initialization.
- **Security & Isolation:** Requires DDL schema privileges.
- **License:** Apache-2.0 (OSI).

#### 9. `openfga`
- **Purpose:** Fine-grained Relationship-Based Access Control (ReBAC) authorization engine.
- **Layers & Capabilities:** Layer 11 (Workspace Isolation), Layer 12 (Fine-Grained Permissions).
- **Mandatory / Optional:** Mandatory for enterprise ReBAC checks.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `openfga-postgres` (healthy), `openfga-migrate` (completed).
- **Persistence Requirements:** Delegated to `openfga-postgres`.
- **Image Size:** 114 MB on disk (27.7 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~30–50 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Stateless API server; queries backing store.
- **Consolidation / Sharing:** Keep OpenFGA binary; point datastore to consolidated PostgreSQL.
- **Security & Isolation:** Store-level and tuple-level authorization checks.
- **License:** Apache-2.0 (OSI).

#### 10. `infisical-postgres`
- **Purpose:** Dedicated PostgreSQL 14 backing datastore for Infisical secret management.
- **Layers & Capabilities:** Layer 12 (Secrets & Key Management).
- **Mandatory / Optional:** Mandatory for standalone Infisical.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `infisical_postgres_data`.
- **Image Size:** ~210 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–60 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `infisical_postgres_data`.
- **Startup Time:** ~2.5s.
- **Availability & Recovery:** Relational WAL durability.
- **Consolidation / Sharing:** Prime candidate to merge into `supabase-db` as database `infisical`.
- **Security & Isolation:** Isolated database user with encrypted secrets storage.
- **License:** PostgreSQL (OSI).

#### 11. `infisical-redis`
- **Purpose:** Dedicated Redis 7.4 cache for Infisical token caching and rate limiting.
- **Layers & Capabilities:** Layer 12 (Secrets Management).
- **Mandatory / Optional:** Mandatory for standalone Infisical.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `infisical_redis_data`.
- **Image Size:** ~35 MB (Redis alpine).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~15–25 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `infisical_redis_data`.
- **Startup Time:** ~0.6s.
- **Availability & Recovery:** Ephemeral cache restart.
- **Consolidation / Sharing:** Consolidate into `valkey` (database 1 or key prefix `infisical:`).
- **Security & Isolation:** Redis auth password.
- **License:** RSALv2 / SSPL-v1 (non-OSI). Consolidating into Valkey eliminates this non-OSI dependency!

#### 12. `infisical`
- **Purpose:** Enterprise secrets management platform, token rotation, and credential encryption.
- **Layers & Capabilities:** Layer 12 (Secrets Management).
- **Mandatory / Optional:** Mandatory for enterprise secret lifecycle; replaceable by local AES-256 encrypted vault or environment variables in Lite profiles.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `infisical-postgres` (healthy), `infisical-redis` (healthy).
- **Persistence Requirements:** Delegated to backing store.
- **Image Size:** 2,810 MB on disk (612 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~180–280 MiB, Node.js runtime).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~5.0s.
- **Availability & Recovery:** Stateless API server; auto-reconnects to backing stores.
- **Consolidation / Sharing:** Keep Infisical in Standard/Enterprise; use built-in encrypted keystore in Lite.
- **Security & Isolation:** AES-256-GCM envelope encryption, audit logging.
- **License:** MIT (OSI).

#### 13. `bytebase`
- **Purpose:** Database schema change management, automated DDL migrations, and SQL review.
- **Layers & Capabilities:** Layer 15 (Platform Infrastructure & Database Operations).
- **Mandatory / Optional:** Mandatory for regulated enterprise schema change management; optional for dev.
- **Continuous / On-Demand:** Continuous in Enterprise; on-demand in Lite/Standard.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `bytebase_data` mounted at `/var/opt/bytebase`.
- **Image Size:** 511 MB on disk (128 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~60–90 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `bytebase_data`.
- **Startup Time:** ~2.8s.
- **Availability & Recovery:** Embedded SQLite or external PostgreSQL database.
- **Consolidation / Sharing:** On-demand activation during migration cycles.
- **Security & Isolation:** RBAC and SQL execution governance.
- **License:** Apache-2.0 (OSI).

#### 14. `kafka`
- **Purpose:** Distributed streaming event log for high-throughput metering, telemetry events, and event bus.
- **Layers & Capabilities:** Layer 10 (Event Sinks), Layer 13 (Billing & Metering Event Pipeline).
- **Mandatory / Optional:** Mandatory for distributed OpenMeter event ingestion; optional for Lite.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None (uses KRaft mode without ZooKeeper).
- **Persistence Requirements:** Named volume `kafka_data` mounted at `/var/lib/kafka/data`.
- **Image Size:** 627 MB on disk (218 MB content).
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~300–450 MiB, JVM runtime).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `kafka_data`.
- **Startup Time:** ~8.0s.
- **Availability & Recovery:** High durability via partition logs and commit offsets.
- **Consolidation / Sharing:** In Lite profiles, Valkey Streams or direct HTTP sync replaces Kafka.
- **Security & Isolation:** SASL/SCRAM authentication, TLS encryption.
- **License:** Apache-2.0 (OSI).

#### 15. `openmeter-postgres`
- **Purpose:** Dedicated PostgreSQL 14 backing datastore for OpenMeter configuration and balance state.
- **Layers & Capabilities:** Layer 13 (Billing & Metering).
- **Mandatory / Optional:** Mandatory for OpenMeter.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `openmeter_postgres_data`.
- **Image Size:** ~210 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–60 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `openmeter_postgres_data`.
- **Startup Time:** ~2.5s.
- **Availability & Recovery:** Relational WAL durability.
- **Consolidation / Sharing:** Consolidate into `supabase-db` as database `openmeter`.
- **Security & Isolation:** Isolated credentials.
- **License:** PostgreSQL (OSI).

#### 16. `openmeter-clickhouse`
- **Purpose:** Dedicated analytical OLAP database for real-time aggregation of metering events.
- **Layers & Capabilities:** Layer 13 (High-Throughput Metering & Aggregations).
- **Mandatory / Optional:** Mandatory for distributed OpenMeter aggregation.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `openmeter_clickhouse_data`.
- **Image Size:** ~650 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~250–400 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `openmeter_clickhouse_data`.
- **Startup Time:** ~4.0s.
- **Availability & Recovery:** MergeTree column-store durability.
- **Consolidation / Sharing:** Can be consolidated with SigNoz ClickHouse in Enterprise, or bypassed with PostgreSQL table aggregation in Lite.
- **Security & Isolation:** User authentication, read-only analytical queries.
- **License:** Apache-2.0 (OSI).

#### 17. `openmeter-redis`
- **Purpose:** Dedicated Redis 7.4 cache for event deduplication in OpenMeter sink.
- **Layers & Capabilities:** Layer 13 (Metering Deduplication).
- **Mandatory / Optional:** Mandatory for OpenMeter deduplication driver.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `openmeter_redis_data`.
- **Image Size:** ~35 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~15–25 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `openmeter_redis_data`.
- **Startup Time:** ~0.6s.
- **Availability & Recovery:** Ephemeral deduplication key store (768h TTL).
- **Consolidation / Sharing:** Consolidate into `valkey` (database 2).
- **Security & Isolation:** Password protected.
- **License:** RSALv2 / SSPL-v1 (non-OSI). Consolidating into Valkey eliminates non-OSI risk!

#### 18. `openmeter`
- **Purpose:** Real-time AI token consumption and usage-based metering API server.
- **Layers & Capabilities:** Layer 13 (Usage Metering & Quotas).
- **Mandatory / Optional:** Mandatory for enterprise usage-based billing.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `kafka` (healthy), `openmeter-clickhouse` (healthy), `openmeter-postgres` (healthy).
- **Persistence Requirements:** Delegated to backing stores.
- **Image Size:** ~95 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–70 MiB, Go binary).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** Mounted configuration configmap.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Stateless API; scales horizontally.
- **Consolidation / Sharing:** Keep in Enterprise; in Lite/Standard use built-in SQLite/Valkey local metering adapter (`control/billing/metering/metering_adapter.py`).
- **Security & Isolation:** API token authentication.
- **License:** Apache-2.0 (OSI).

#### 19. `openmeter-sink-worker`
- **Purpose:** Consumes token consumption events from Kafka and flushes batches into ClickHouse.
- **Layers & Capabilities:** Layer 13 (Billing Pipeline).
- **Mandatory / Optional:** Mandatory for distributed OpenMeter ingestion.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `kafka`, `openmeter-clickhouse`, `openmeter`, `openmeter-redis`.
- **Persistence Requirements:** None (commits Kafka offsets).
- **Image Size:** ~95 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~30–50 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Resumes from committed Kafka offset.
- **Consolidation / Sharing:** Bypassed in Lite profiles.
- **Security & Isolation:** Internal network only.
- **License:** Apache-2.0 (OSI).

#### 20. `openmeter-balance-worker`
- **Purpose:** Real-time customer balance calculations and credit deduction worker.
- **Layers & Capabilities:** Layer 13 (Billing Pipeline).
- **Mandatory / Optional:** Mandatory when balance credit limits are enforced via OpenMeter.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `kafka`, `openmeter-clickhouse`, `openmeter`, `openmeter-redis`.
- **Persistence Requirements:** None.
- **Image Size:** ~95 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~30–50 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Automatic recovery.
- **Consolidation / Sharing:** Can be disabled if credit settlement is handled by Lago/HyperSwitch.
- **Security & Isolation:** Internal network only.
- **License:** Apache-2.0 (OSI).

#### 21. `openmeter-billing-worker`
- **Purpose:** Automated billing invoice triggering worker based on meter thresholds.
- **Layers & Capabilities:** Layer 13 (Billing Pipeline).
- **Mandatory / Optional:** Mandatory for automated invoice sync.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `kafka`, `openmeter-clickhouse`, `openmeter`.
- **Persistence Requirements:** None.
- **Image Size:** ~95 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~30–50 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Automatic recovery.
- **Consolidation / Sharing:** Can be disabled in dev/lite profiles.
- **Security & Isolation:** Internal network only.
- **License:** Apache-2.0 (OSI).

#### 22. `openmeter-jobs`
- **Purpose:** Background recurring maintenance tasks, partition lifecycle, and aggregation rollup jobs.
- **Layers & Capabilities:** Layer 13 (Billing Pipeline).
- **Mandatory / Optional:** Mandatory for OpenMeter table rollups.
- **Continuous / On-Demand:** Continuous scheduler.
- **Startup Dependencies:** `openmeter`, `kafka`, `openmeter-clickhouse`, `openmeter-postgres`.
- **Persistence Requirements:** None.
- **Image Size:** ~95 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~30–50 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Job runner loop.
- **Consolidation / Sharing:** Can be triggered on-demand via cron rather than continuous daemon.
- **Security & Isolation:** Internal network only.
- **License:** Apache-2.0 (OSI).

#### 23. `lago-postgres`
- **Purpose:** Dedicated PostgreSQL 14 backing datastore for Lago billing engine (invoices, subscriptions, customers).
- **Layers & Capabilities:** Layer 13 (Billing & Subscription Management).
- **Mandatory / Optional:** Mandatory for standalone Lago.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `lago_postgres_data`.
- **Image Size:** ~210 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–60 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `lago_postgres_data`.
- **Startup Time:** ~2.5s.
- **Availability & Recovery:** Relational WAL durability.
- **Consolidation / Sharing:** Consolidate into `supabase-db` as database `lago`.
- **Security & Isolation:** Placed on isolated network `agpl_quarantine_net`.
- **License:** PostgreSQL (OSI).

#### 24. `lago-redis`
- **Purpose:** Dedicated Redis 6 cache for Lago billing background worker queues (Sidekiq).
- **Layers & Capabilities:** Layer 13 (Billing Background Tasks).
- **Mandatory / Optional:** Mandatory for Lago Sidekiq queues.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `lago_redis_data`.
- **Image Size:** ~30 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~15–25 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `lago_redis_data`.
- **Startup Time:** ~0.6s.
- **Availability & Recovery:** Ephemeral task queue persistence.
- **Consolidation / Sharing:** Consolidate into `valkey` (database 3) on `agpl_quarantine_net`.
- **Security & Isolation:** Isolated network `agpl_quarantine_net`.
- **License:** BSD-3-Clause (OSI).

#### 25. `lago-migrate`
- **Purpose:** Executes Rails schema migrations for Lago billing database.
- **Layers & Capabilities:** Layer 13 (Billing Database Setup).
- **Mandatory / Optional:** Transient one-shot migration job.
- **Continuous / On-Demand:** Runs once at startup (`restart: on-failure`).
- **Startup Dependencies:** `lago-postgres` (healthy), `lago-redis` (healthy).
- **Persistence Requirements:** Ephemeral.
- **Image Size:** ~450 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Exits after migration completes).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~6.0s (Rails boot & migrate).
- **Availability & Recovery:** Exit 0 on success.
- **Consolidation / Sharing:** Keep as one-shot init container.
- **Security & Isolation:** AGPL-3.0 quarantine boundary; database migration credentials.
- **License:** AGPL-3.0 (OSI).

#### 26. `lago`
- **Purpose:** Open-source metering and billing API platform (subscriptions, coupons, customer ledger).
- **Layers & Capabilities:** Layer 13 (Billing Platform API).
- **Mandatory / Optional:** Mandatory for full subscription billing.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `lago-postgres` (healthy), `lago-redis` (healthy), `lago-migrate` (completed).
- **Persistence Requirements:** Delegated to `lago-postgres`.
- **Image Size:** ~450 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~160–240 MiB, Ruby on Rails Puma server).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** Named volume `lago_api_data`.
- **Startup Time:** ~6.5s.
- **Availability & Recovery:** Web API server with automatic container restart.
- **Consolidation / Sharing:** AGPL-3.0 quarantine boundary: interacts strictly via external HTTP REST API; zero library linking.
- **Security & Isolation:** Network isolated on `agpl_quarantine_net`.
- **License:** AGPL-3.0 (OSI).

#### 27. `lago-worker`
- **Purpose:** Asynchronous billing worker (Sidekiq) processing invoice generation, PDF exports, and webhook delivery.
- **Layers & Capabilities:** Layer 13 (Billing Async Processing).
- **Mandatory / Optional:** Mandatory when Lago is running.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `lago` (healthy).
- **Persistence Requirements:** None.
- **Image Size:** ~450 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~140–200 MiB, Sidekiq worker).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~5.5s.
- **Availability & Recovery:** Retries failed jobs via Sidekiq queue.
- **Consolidation / Sharing:** Can be scaled to 0 in dev environments where async billing is not required.
- **Security & Isolation:** Network isolated on `agpl_quarantine_net`.
- **License:** AGPL-3.0 (OSI).

#### 28. `librechat-mongodb`
- **Purpose:** Dedicated MongoDB 7.0 database for LibreChat user sessions, conversations, and presets.
- **Layers & Capabilities:** Layer 18 (Surface Chat Interface).
- **Mandatory / Optional:** Mandatory for standalone LibreChat.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `librechat_mongodb_data`.
- **Image Size:** ~720 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~150–250 MiB, WiredTiger cache).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `librechat_mongodb_data`.
- **Startup Time:** ~3.0s.
- **Availability & Recovery:** B-tree journaling and document store durability.
- **Consolidation / Sharing:** For Lite profiles where UI is optional, disable LibreChat + MongoDB entirely (saves ~450+ MiB idle RAM!).
- **Security & Isolation:** Internal network, MongoDB auth credentials.
- **License:** SSPL-v1 (non-OSI). Disabling in default/lite removes this non-OSI runtime.

#### 29. `librechat`
- **Purpose:** Multi-model open-source web chat user interface and conversational playground.
- **Layers & Capabilities:** Layer 18 (Surface Chat Interface).
- **Mandatory / Optional:** Optional UI surface; core platform operates headlessly via REST/WebSocket/CLI APIs.
- **Continuous / On-Demand:** Continuous when user interaction UI is needed; on-demand otherwise.
- **Startup Dependencies:** `librechat-mongodb` (healthy).
- **Persistence Requirements:** Named volume `librechat_uploads` for multimodal user attachments.
- **Image Size:** ~850 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~120–180 MiB, Node.js runtime).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `librechat_uploads`.
- **Startup Time:** ~4.0s.
- **Availability & Recovery:** Web frontend restart.
- **Consolidation / Sharing:** Can be started on-demand via `--profile ui` rather than running continuously in core profile.
- **Security & Isolation:** Configured with host-gateway networking to route to local reasoning gateway.
- **License:** MIT (OSI).

#### 30. `otel-collector`
- **Purpose:** OpenTelemetry Collector receiving OTLP traces, metrics, and logs from all Central Intelligence layers.
- **Layers & Capabilities:** Layer 14 (Telemetry & Observability).
- **Mandatory / Optional:** Mandatory for unified enterprise observability pipeline.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `ingester` (SigNoz ingester) (condition: `service_healthy`).
- **Persistence Requirements:** Ephemeral in-memory batch buffers.
- **Image Size:** ~65 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~35–60 MiB, Go collector).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** Mounted YAML configuration.
- **Startup Time:** ~1.0s.
- **Availability & Recovery:** In-memory queue with bounded retry and backpressure.
- **Consolidation / Sharing:** In Lite profiles, OTel collector can export directly to local file or stdout without starting heavy ClickHouse/SigNoz backend.
- **Security & Isolation:** Ingests internal telemetry only.
- **License:** Apache-2.0 (OSI).

#### 31. `ingester` (SigNoz OTel Collector Ingester)
- **Purpose:** High-throughput OTel Collector ingesting telemetry data and writing batches into ClickHouse.
- **Layers & Capabilities:** Layer 14 (Observability Telemetry Pipeline).
- **Mandatory / Optional:** Mandatory for SigNoz observability backend.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `signoz-signoz-0` (healthy), `signoz-telemetrystore-clickhouse-0-0` (healthy), `signoz-telemetrystore-migrator` (completed).
- **Persistence Requirements:** None.
- **Image Size:** ~180 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~50–90 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** Mounted configuration.
- **Startup Time:** ~2.0s.
- **Availability & Recovery:** Retries ClickHouse inserts with memory limiter processor.
- **Consolidation / Sharing:** Belongs in `enterprise-observability` profile.
- **Security & Isolation:** Telemetry data privacy filtering.
- **License:** Apache-2.0 (OSI).

#### 32. `signoz-metastore-postgres-0`
- **Purpose:** Dedicated PostgreSQL 16 backing datastore for SigNoz dashboard definitions, alert rules, and user metadata.
- **Layers & Capabilities:** Layer 14 (Observability Metadata).
- **Mandatory / Optional:** Mandatory for SigNoz.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `signoz_metastore_data`.
- **Image Size:** ~230 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~40–60 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `signoz_metastore_data`.
- **Startup Time:** ~2.5s.
- **Availability & Recovery:** Relational WAL durability.
- **Consolidation / Sharing:** Consolidate into `supabase-db` as database `signoz_metastore`.
- **Security & Isolation:** Internal database credentials.
- **License:** PostgreSQL (OSI).

#### 33. `signoz-signoz-0`
- **Purpose:** SigNoz query-service backend and frontend web UI for APM traces, metrics, service graphs, and logs.
- **Layers & Capabilities:** Layer 14 (Observability UI & APM).
- **Mandatory / Optional:** Mandatory for SigNoz visualization.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `signoz-metastore-postgres-0` (healthy), `signoz-telemetrystore-clickhouse-0-0` (healthy), `signoz-telemetrystore-migrator` (completed).
- **Persistence Requirements:** None.
- **Image Size:** ~260 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~90–150 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~3.5s.
- **Availability & Recovery:** Stateless query server.
- **Consolidation / Sharing:** Belongs in `enterprise-observability` profile.
- **Security & Isolation:** Web UI login credentials.
- **License:** MIT / Apache-2.0.

#### 34. `signoz-telemetrykeeper-clickhousekeeper-0`
- **Purpose:** Lightweight consensus service (Raft protocol) replacing ZooKeeper for ClickHouse cluster coordination.
- **Layers & Capabilities:** Layer 14 (Observability Storage Coordination).
- **Mandatory / Optional:** Mandatory for SigNoz ClickHouse cluster.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Named volume `signoz_keeper_data`.
- **Image Size:** ~650 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~60–100 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `signoz_keeper_data`.
- **Startup Time:** ~2.0s.
- **Availability & Recovery:** Raft log state persistence.
- **Consolidation / Sharing:** For standalone single-node deployments, Keeper can be avoided with standalone ClickHouse configuration.
- **Security & Isolation:** Internal Raft port only.
- **License:** Apache-2.0 (OSI).

#### 35. `signoz-telemetrystore-clickhouse-0-0`
- **Purpose:** Primary ClickHouse column-store server holding all trace spans, metrics series, and structured logs.
- **Layers & Capabilities:** Layer 14 (Observability OLAP Storage).
- **Mandatory / Optional:** Mandatory for SigNoz storage.
- **Continuous / On-Demand:** Continuous.
- **Startup Dependencies:** `signoz-telemetrykeeper-clickhousekeeper-0` (healthy), `signoz-telemetrystore-clickhouse-user-scripts` (completed).
- **Persistence Requirements:** Named volume `signoz_clickhouse_data`.
- **Image Size:** ~650 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Projected ~300–550 MiB).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** `signoz_clickhouse_data`.
- **Startup Time:** ~4.0s.
- **Availability & Recovery:** MergeTree file integrity.
- **Consolidation / Sharing:** Prime memory consumer. Bypassed in Lite/Standard profiles to save >500 MiB RAM.
- **Security & Isolation:** Authenticated ClickHouse users.
- **License:** Apache-2.0 (OSI).

#### 36. `signoz-telemetrystore-clickhouse-user-scripts`
- **Purpose:** Initializes users, roles, and schema permissions on ClickHouse startup.
- **Layers & Capabilities:** Layer 14 (Observability Storage Setup).
- **Mandatory / Optional:** Transient one-shot initialization job.
- **Continuous / On-Demand:** Runs once at startup.
- **Startup Dependencies:** None.
- **Persistence Requirements:** Ephemeral.
- **Image Size:** ~650 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Exits immediately upon completion).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** Mounted SQL script.
- **Startup Time:** ~1.5s.
- **Availability & Recovery:** Exit 0 on success.
- **Consolidation / Sharing:** One-shot script.
- **Security & Isolation:** Admin credentials.
- **License:** Apache-2.0 (OSI).

#### 37. `signoz-telemetrystore-migrator`
- **Purpose:** Executes database migrations for SigNoz telemetry schemas on ClickHouse.
- **Layers & Capabilities:** Layer 14 (Observability Schema Management).
- **Mandatory / Optional:** Transient one-shot migration job.
- **Continuous / On-Demand:** Runs once at startup.
- **Startup Dependencies:** `signoz-telemetrystore-clickhouse-0-0` (healthy).
- **Persistence Requirements:** Ephemeral.
- **Image Size:** ~180 MB.
- **Measured Idle RAM:** **NOT MEASURED** (Exits immediately upon completion).
- **Measured Active/Peak RAM:** **NOT MEASURED**.
- **Measured CPU:** **NOT MEASURED**.
- **Disk/Volume:** None.
- **Startup Time:** ~2.0s.
- **Availability & Recovery:** Exit 0 on success.
- **Consolidation / Sharing:** One-shot script.
- **Security & Isolation:** Admin credentials.
- **License:** Apache-2.0 (OSI).

---

### 3.2 Optional Profile Services (14 Services)

| # | Service Name | Image | SPDX License | Purpose & Capabilities | Measured Idle RAM | Projected Idle RAM |
|---|---|---|---|---|---:|---:|
| 38 | `ollama` | `ollama/ollama:0.40.16` | MIT | Local offline LLM inference runner (L4/L6) | **NOT MEASURED** | ~400–1,200+ MiB (model dependent) |
| 39 | `meilisearch` | `getmeili/meilisearch:v1.7.3` | MIT | Typo-tolerant fast BM25 lexical search engine (L3) | **NOT MEASURED** | ~40–80 MiB |
| 40 | `chroma` | `chromadb/chroma:0.4.22` | Apache-2.0 | Alternative lightweight vector store (L2/L3) | **NOT MEASURED** | ~60–110 MiB |
| 41 | `memgraph` | `memgraph/memgraph-platform:2.14.1` | BSL-1.1 | In-memory graph analytics & visualization (L2/L3) | **NOT MEASURED** | ~180–300 MiB |
| 42 | `falkordb` | `falkordb/falkordb:v4.22.3` | SSPL-v1 | Low-latency graph database on Redis module (L2/L3) | **NOT MEASURED** | ~50–90 MiB |
| 43 | `nango` | `nangohq/nango-server:hosted-0.72.4` | Elastic-2.0 | 250+ pre-built SaaS OAuth connector orchestrator (L7) | **NOT MEASURED** | ~120–200 MiB |
| 44 | `phoenix` | `arizephoenix/phoenix:version-21.0.0` | Elastic-2.0 | LLM evaluation, prompt tracing & drift analysis (L11) | **NOT MEASURED** | ~150–250 MiB |
| 45 | `hyperswitch` | `juspaydotin/hyperswitch-router:...` | Apache-2.0 | Payment routing, card tokenization, fraud checks (L13) | **NOT MEASURED** | ~120–200 MiB |
| 46 | `livekit` | `livekit/livekit-server:v1.13.11` | Apache-2.0 | Realtime WebRTC audio/video SFU streaming server (L1) | **NOT MEASURED** | ~45–80 MiB |
| 47 | `huly` | `hardcoreeng/front:v0.7.432` | EPL-2.0 | Enterprise collaborative workspace & project tracker (L9) | **NOT MEASURED** | ~110–180 MiB |
| 48 | `svix` | `svix/svix-server:v1.105.0` | MIT | Enterprise webhook gateway with replay & HMAC (L10) | **NOT MEASURED** | ~35–60 MiB |
| 49 | `dragonfly` | `docker.dragonflydb.io/...` | BSL-1.1 | High-throughput multi-threaded Redis replacement (L2) | **NOT MEASURED** | ~60–120 MiB |
| 50 | `uptime-kuma` | `louislam/uptime-kuma:1.23.13` | MIT | Standalone synthetic uptime monitor and status page (L14) | **NOT MEASURED** | ~40–70 MiB |
| 51 | `posthog` | `posthog/posthog:latest-release` | MIT | Product analytics, feature flagging & session replay (L14) | **NOT MEASURED** | ~350–700 MiB |

---

## 4. Resource Totals & Deficit Analysis

### 4.1 Structural Duplication in Current Core Profile
The current `core` profile suffers from severe component sprawl:
- **7 Separate PostgreSQL Instances:** `supabase-db`, `apache-age`, `openfga-postgres`, `infisical-postgres`, `lago-postgres`, `openmeter-postgres`, `signoz-metastore-postgres-0`.
- **4 Separate Redis / Valkey Instances:** `valkey`, `infisical-redis`, `lago-redis`, `openmeter-redis`.
- **2 Separate ClickHouse Instances + 1 Keeper:** `openmeter-clickhouse`, `signoz-telemetrystore-clickhouse-0-0`, `signoz-telemetrykeeper-clickhousekeeper-0`.
- **2 Heavy JVM Runtimes:** `kafka`, `keycloak`.
- **1 Dedicated MongoDB Instance:** `librechat-mongodb`.

### 4.2 Resource Balance Sheet

| Metric | Measured Baseline (2 Services Running) | Current Unconstrained Core Profile (37 Services, Projected) | Local PC Capacity Limits | Status |
|---|---:|---:|---:|---|
| **Active Running Services** | 2 | 37 | 6–10 max safe | **Exceeds Capacity** |
| **Idle Memory (RAM)** | **144.39 MiB** (empirically measured) | **~3,850 – 5,450 MiB** (Projected) | 3,812 MiB (3.72 GiB limit) | **CRITICAL DEFICIT (OOM 137)** |
| **Peak Memory (RAM)** | **NOT MEASURED** | **~8,000 – 14,000 MiB** (Projected) | 3,812 MiB limit | **UNRUNNABLE ON PC** |
| **Idle CPU Utilization** | 0.97% (empirically measured) | ~15–35% continuous polling | 4 cores / 8 threads | **Severe Contention** |
| **Total Image Disk Space** | ~965 MB | >11,500 MB (~11.5 GB) | Local SSD ample | Manageable |

### 4.3 Key Architectural Takeaway
**Starting the unconstrained 37-service core profile on the local Windows PC is mathematically impossible without memory exhaustion.** Central Intelligence requires an immediate, backwards-compatible profile partitioning architecture (`lite`, `standard`, `enterprise`) and database/cache consolidation to operate durably within available hardware constraints.
