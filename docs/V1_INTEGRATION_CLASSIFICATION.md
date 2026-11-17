# CENTRAL INTELLIGENCE V1 — INTEGRATION CLASSIFICATION & MODULARITY MATRIX

**Author:** Staff Principal Architect & Systems Reliability Auditor  
**Scope:** Categorization, Modularity Analysis, and Replacement Roadmap for all Integrations  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **PROPOSAL & CLASSIFICATION COMPLETE — PENDING ARCHITECTURAL SIGN-OFF**  

---

## 1. Architectural Rule & Classification Framework

### The Fundamental Capability vs. Implementation Rule
> **A mandatory capability does not automatically make its current third-party implementation mandatory.**  
> Central Intelligence must remain modular, configurable, and capable of replacing underlying third-party implementations without rewriting or destabilizing the platform.

Central Intelligence delivers a 19-layer cognitive architecture. Each capability (e.g., ReBAC authorization, secret lifecycle management, persistent facts storage, semantic vector retrieval, workflow replay) represents an architectural requirement. However, third-party software packages (e.g., OpenFGA, Infisical, Lago, OpenMeter, SigNoz, Temporal) are merely **pluggable implementations** conforming to clean domain contracts.

### The 5 Standard Classification Tiers

Every integration and dependency is categorized into one of five mutually exclusive tiers:

```
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| Tier                              | Definition & Operational Policy                                                                    |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| 1. Mandatory Core Implementation  | An indispensable capability where the current engine serves as the foundational production driver.  |
|                                   | Cannot be removed without replacing the core operational fabric of Central Intelligence.           |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| 2. Replaceable Core Implementation| A strictly mandatory architectural capability, but currently backed by a swappable or heavyweight  |
|                                   | third-party provider that can be substituted with a native, embedded, or alternative engine.       |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| 3. Optional Integration           | A capability that adds business value, surface interaction, or enterprise convenience, but whose   |
|                                   | absence does not impair core reasoning, agent execution, or platform safety.                      |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| 4. Development/Testing-Only Tool  | Scaffolding, CLI automation, mock servers, or local inspection tools used during engineering, CI,  |
|                                   | and deployment orchestration, not loaded as long-running production daemons.                       |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
| 5. Redundant or Removable         | Unnecessary duplication, non-OSI license conflicts, or legacy engines completely superseded by     |
|                                   | lighter, OSI-compliant native implementations.                                                     |
+-----------------------------------+----------------------------------------------------------------------------------------------------+
```

---

## 2. Master Classification Matrix

| Dependency / Service | Current Layer | Capability Provided | Assigned Classification | Primary Reason for Classification | Current Abstraction Interface | Native / Lightweight Alternative |
|---|:---:|---|---|---|---|---|
| **PostgreSQL** | L15 | Relational persistence, ACID transactions, RLS | **1. Mandatory Core Implementation** (Multi-tenant) | Indispensable multi-tenant production system of record. | `SupabaseAdapter`, `asyncpg` | SQLite with WAL (for embedded edge setups) |
| **Valkey** | L1 / L2 | Fast memory cache, session turns, rate limiting | **1. Mandatory Core Implementation** (Distributed) | Foundational low-latency distributed state (BSD-3-Clause, 6.5 MiB RAM). | `BaseWorkingMemory`, `RedisWorkingMemory` | `InMemoryWorkingMemory` (pure Python in-memory) |
| **Docker Sandbox** | L3 / L5 | Untrusted code isolation & sandbox execution | **1. Mandatory Core Implementation** (Local Node) | Essential security boundary preventing host system compromise from agent code. | `BaseDeviceRunner`, `DockerExecutionEngine` | Wasmtime (WebAssembly micro-sandbox) |
| **OpenFGA** | L12 | Fine-grained ReBAC relationship authorization | **2. Replaceable Core Implementation** | ReBAC is mandatory; OpenFGA server is swappable with embedded Zanzibar engine. | `OpenFGAAdapter` (canonical tuples) | SQLite/PostgreSQL recursive CTE Zanzibar engine |
| **Infisical** | L12 | Secret vault, BYOK encryption, key rotation | **2. Replaceable Core Implementation** | Secret vaulting is mandatory; Node.js Infisical daemon is swappable with local KMS. | `InfisicalAdapter` (generic KV vault) | AES-256-GCM envelope vault in SQLite |
| **SigNoz** | L14 | OpenTelemetry APM, traces, and metrics | **2. Replaceable Core Implementation** | Telemetry is mandatory; SigNoz ClickHouse cluster is just one OTLP consumer. | `SigNozAdapter` (`opentelemetry-sdk`) | Standard OTel Collector, Jaeger, or local JSON-L |
| **Temporal** | L8 / L19 | Crash-resilient durable workflow execution | **2. Replaceable Core Implementation** | Durable orchestration is mandatory; Temporal is swappable with WAL checkpoints. | `BaseOrchestratorBridge` | Enhanced `OrchestratorBridge` with SQLite checkpoints |
| **Qdrant** | L2 / L3 | Semantic vector database with payload filters | **2. Replaceable Core Implementation** | Vector search is mandatory; Qdrant is swappable with pgvector or Qdrant `:memory:`. | `BaseVectorStore`, `QdrantAdapter` | Embedded Qdrant (`:memory:`), `pgvector` |
| **pgvector** | L15 | In-database PostgreSQL vector similarity | **2. Replaceable Core Implementation** | Vector search is mandatory; pgvector is co-located alternative to Qdrant. | `SupabaseAdapter`, `extended_pg_vector` | Qdrant, sqlite-vec |
| **Apache AGE** | L2 / L3 | OpenCypher graph database for GraphRAG | **2. Replaceable Core Implementation** | Graph traversal is mandatory for GraphRAG; swappable with NetworkX / Kùzu. | `BaseGraphStore`, `ApacheAGEGraphAdapter` | `NetworkXGraphFallback` (already in codebase), Kùzu |
| **Lago** | L13 | Subscription plans, wallet, invoice billing | **3. Optional Integration** | Agent intelligence operates independently of billing; needed only for commercial SaaS. | `LagoAdapter` (boundary HTTP REST) | Embedded Python billing ledger; Stripe direct API |
| **OpenMeter** | L13 | Streaming CloudEvents token metering | **3. Optional Integration** | Token accounting is required for SaaS, but Kafka/ClickHouse is overkill for small deployments. | `OpenMeterAdapter` (CloudEvents 1.0) | Asynchronous PostgreSQL/Valkey stream token ledger |
| **Bytebase** | L17 | Database DevOps, SQL review, rollout/rollback | **3. Optional Integration** | CI schema migration can run via lightweight scripts; web review portal is an enterprise extra. | `BytebaseAdapter` (DDL migration runner) | Alembic migrations directly in CI pipelines |
| **LibreChat** | L18 | Multi-provider ChatGPT-style web UI | **3. Optional Integration** | Surface UI client; gateway functions via API, CLI, or desktop without it. | `LibreChatAdapter` (gateway proxy) | Native React/Svelte Web UI; Jan Desktop; CLI |
| **Keycloak** | L12 | Enterprise SAML/OIDC SSO, WebAuthn Passkeys | **3. Optional Integration** | Enterprise federated login; standard API key / JWT authentication works without Keycloak. | `KeycloakAdapter` | Native JWT auth; Auth0; Authentik |
| **Apache Kafka** | L15 | High-throughput distributed event bus | **3. Optional Integration** | Only required when OpenMeter streaming is activated. | `AutoMQAdapter` | Valkey Streams; RabbitMQ; Postgres LISTEN/NOTIFY |
| **ClickHouse** | L13/L14 | Columnar OLAP engine for events and traces | **3. Optional Integration** | Heavy analytical database needed only at massive log/metering scale (>10M events/day). | Direct DB connections in sub-services | DuckDB (embedded OLAP); PostgreSQL partitioning |
| **Chroma** | L2 | Embedded vector store | **3. Optional Integration** | Alternative vector store for local development. | `BaseVectorStore`, `ChromaAdapter` | Qdrant `:memory:`, pgvector |
| **Meilisearch** | L3 | Instant full-text search engine | **3. Optional Integration** | High-performance keyword search; complements vector search. | `BaseSearchEngine` | PostgreSQL `tsvector` full-text search; SQLite FTS5 |
| **Ollama** | L9 / L16 | Local on-device LLM runtime | **3. Optional Integration** | Required only for local offline model serving; swappable with cloud API endpoints. | `OllamaContextAdapter`, OpenAI-compatible client | vLLM; llama.cpp; Cloud LLM APIs (Gemini, Claude, GPT) |
| **Arize Phoenix** | L11 | LLM evaluation and hallucination tracing | **3. Optional Integration** | Specialized evaluation tool; non-OSI license (Elastic-2.0). | `PhoenixAdapter` | OTel Collector + Langfuse / OpenInference |
| **PostHog** | L14 | Product analytics and conversion funnels | **3. Optional Integration** | User behavior tracking; completely optional for core platform functionality. | `PostHogAdapter` | Local SQLite analytics; Cloud PostHog |
| **Svix** | L15 | Outbound webhook delivery engine | **3. Optional Integration** | Ensures reliable webhook delivery; can be handled by async task worker. | Webhook client | Celery / Valkey async HTTP worker with retry logic |
| **Huly** | L19 | Collaborative team PM and issue tracker | **3. Optional Integration** | Agent-to-human task handoff; optional federation partner. | `HulyAdapter` | GitHub Issues; Linear; Jira |
| **LiveKit** | L1 / L10 | WebRTC real-time voice and media server | **3. Optional Integration** | Low-latency duplex voice; unnecessary for text, chat, and reasoning workflows. | `LiveKitAdapter` | Deepgram / ElevenLabs direct WebSocket streaming |
| **Hyperswitch** | L13 | Universal payment routing switch | **3. Optional Integration** | Multi-processor card routing; optional for non-commercial or Stripe-only setups. | `HyperswitchAdapter` | Direct Stripe / PayPal API SDK |
| **Coolify** | L17 | Self-hosted PaaS container manager | **3. Optional Integration** | Web-based container deployment; external deployment tool. | `CoolifyAdapter` | Docker Compose; Kamal; Kubernetes |
| **GrowthBook** | L17 | Feature flags and canary experimentation | **3. Optional Integration** | Dynamic flag toggling; adapter already includes local deterministic fallback. | `GrowthBookAdapter` | Local config / environment variable toggles |
| **Jan Desktop** | L18 | Local desktop application interface | **3. Optional Integration** | Desktop frontend surface; completely decoupled from backend. | `JanDesktopAdapter` | Web UI; CLI |
| **E2B** | L3 / L5 | Cloud-isolated code interpreter | **3. Optional Integration** | Paid cloud alternative to local Docker sandbox. | `BaseDeviceRunner`, `E2BExecutionEngine` | Local Docker sandbox (zero cost) |
| **MongoDB** | L18 | Document database for LibreChat state | **3. Optional Integration** | Solely an internal dependency of LibreChat; non-OSI license (SSPL-v1). | Direct driver in LibreChat Node.js | PostgreSQL JSONB; SQLite |
| **Kamal** | L17 | Zero-downtime container deployment CLI | **4. Dev/Testing-Only Tool** | CLI release orchestrator executed during CI deployment; not a runtime server. | `KamalAdapter` | Docker Swarm; Kubernetes; Shell deploy script |
| **Uptime Kuma** | L14 | Operational service uptime monitor | **4. Dev/Testing-Only Tool** | Developer/operator dashboard for pinging HTTP endpoints. | Web UI | Prometheus blackbox exporter; AWS Route53 health checks |
| **Dragonfly** | L15 | In-memory cache engine | **5. Redundant or Removable** | Non-OSI (BSL-1.1); Valkey provides identical functionality with BSD-3-Clause license. | Standard Redis wire | **Valkey 8.0.2** |
| **Memgraph** | L2 | In-memory graph database | **5. Redundant or Removable** | Non-OSI (BSL-1.1); Apache AGE (Apache-2.0) and NetworkX fulfill all graph needs. | `BaseGraphStore` | **Apache AGE** or **NetworkX** |
| **FalkorDB** | L3 | Graph database on Redis | **5. Redundant or Removable** | Non-OSI (SSPL-v1); superseded by Apache AGE. | `BaseGraphStore` | **Apache AGE** |
| **Duplicated Postgres** (x5)| Various | Isolated databases for sub-services | **5. Redundant or Removable (Consolidatable)** | Running 6 distinct Postgres servers wastes >500 MiB RAM. | Standard Postgres | **Consolidate into `supabase-db` via multiple schemas** |
| **Duplicated Redis** (x3) | Various | Isolated caches for sub-services | **5. Redundant or Removable (Consolidatable)** | Running 4 distinct Redis/Valkey servers wastes memory and introduces SSPL Redis. | Standard Redis wire | **Consolidate into `valkey` via logical DB indexes** |

---

## 3. Modularity & Decoupling Strategy

To guarantee that Central Intelligence remains independent of specific vendors, five core domains must formalize their modular boundaries:

```
+----------------------------------------------------------------------------------------------------+
| DOMAIN ABSTRACTION ARCHITECTURE                                                                    |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Identity Domain]        [Secrets Domain]        [Orchestration]      [Vector Search]             |
|          |                       |                       |                     |                   |
|  +---------------+       +---------------+       +---------------+     +---------------+           |
|  | BaseAuthz     |       | BaseSecret    |       | BaseWorkflow  |     | BaseVector    |           |
|  | Engine        |       | Vault         |       | Bridge        |     | Store         |           |
|  +---------------+       +---------------+       +---------------+     +---------------+           |
|    |           |           |           |           |           |         |           |             |
|    v           v           v           v           v           v         v           v             |
| +--------+  +--------+  +--------+  +--------+  +--------+  +--------+ +-------+  +-------+        |
| |OpenFGA |  |Embedded|  |Infisical| |Embedded|  |Temporal|  |Native  | |Qdrant |  |pgvector|       |
| |Adapter |  |Zanzibar|  |Adapter |  |AES Vault| |Adapter |  |SQLite  | |Adapter|  |       |        |
| +--------+  +--------+  +--------+  +--------+  +--------+  +--------+ +-------+  +-------+        |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3.1. ReBAC Authorization Decoupling (OpenFGA)
- **Current State:** `OpenFGAAdapter` is directly instantiated. When `ENVIRONMENT=production`, it requires a live OpenFGA server on port 8081.
- **Proposed Architecture:** Introduce `BaseAuthorizationEngine(ABC)` with standard methods:
  - `check_permission(user: str, relation: str, object: str, context: dict) -> bool`
  - `write_tuples(tuples: List[RelationshipTuple]) -> None`
  - `delete_tuples(tuples: List[RelationshipTuple]) -> None`
  - `expand_users(relation: str, object: str) -> List[str]`
- **Implementations:**
  1. `OpenFGAProvider`: Connects to external OpenFGA server (Enterprise profile).
  2. `NativeSqlZanzibarProvider`: Uses a single table `rebac_tuples(user, relation, object)` in PostgreSQL or SQLite with recursive Common Table Expressions (CTE) to perform hierarchical graph resolution in <2ms with zero external services.

### 3.2. Secret Vault Decoupling (Infisical)
- **Current State:** `InfisicalAdapter` communicates with Infisical REST API. In production, an unreachable Infisical daemon halts startup.
- **Proposed Architecture:** Formalize `BaseSecretVault(ABC)`:
  - `store_secret(key: str, value: str, tenant_id: str, app_id: Optional[str]) -> ScopedSecret`
  - `get_secret(key: str, tenant_id: str, app_id: Optional[str]) -> str`
  - `rotate_secret(key: str, new_value: str, tenant_id: str) -> SecretVersion`
- **Implementations:**
  1. `InfisicalSecretVault`: Enterprise distributed vault.
  2. `EnvelopeCryptoVault`: Local AES-256-GCM envelope encryption storing ciphertext in a dedicated `vault_secrets` table in SQLite/PostgreSQL, using a master key from environment or HSM. Eliminates the need for Node.js, Postgres, and Redis containers.

### 3.3. Durable Orchestration Decoupling (Temporal)
- **Current State:** `BaseOrchestratorBridge` is already defined in `control/orchestration/workflow_builder/core/interfaces.py`. `TemporalWorkflowAdapter` and `OrchestratorBridge` both inherit from it.
- **Proposed Architecture:** Expand `OrchestratorBridge` to include **durable checkpoint persistence**:
  - `SQLiteWorkflowStateStore`: Serializes DAG state transitions to SQLite (`.temporal_checkpoints/durable_state.db`).
  - Upon process restart, `OrchestratorBridge.resume(workflow_id)` reloads completed nodes and executes remaining DAG branches, matching Temporal's restart resilience without running a Temporal server container.

### 3.4. Token Metering Decoupling (OpenMeter)
- **Current State:** `OpenMeterAdapter` formats CloudEvents 1.0 JSON payloads and posts to OpenMeter API.
- **Proposed Architecture:** Formalize `BaseTokenMeter(ABC)`:
  - `record_event(event: TokenUsageEvent) -> None`
  - `get_usage(user_id: str, start_time: float, end_time: float) -> MeteredUsageSummary`
- **Implementations:**
  1. `OpenMeterProvider`: Dispatches to OpenMeter + Kafka + ClickHouse for massive scale.
  2. `PostgresStreamMeter`: Appends events to a partitioned `token_usage_events` table in PostgreSQL or local SQLite timeseries, using background batch flushing.

### 3.5. Distributed Tracing Decoupling (SigNoz)
- **Current State:** `SigNozAdapter` configures `opentelemetry-sdk` to export via HTTP to port 4318.
- **Proposed Architecture:** The adapter already uses standard OpenTelemetry. Simply rename `SigNozAdapter` to `OpenTelemetryAdapter` and configure `OTEL_EXPORTER_OTLP_ENDPOINT`. Any compliant endpoint (SigNoz, Grafana Tempo, Jaeger, Datadog, Honeycomb) or an in-memory JSON-L ring buffer can be targeted seamlessly.

---

## 4. Consolidation & Footprint Optimization Plan

### 4.1. Database Consolidation (Eliminating 5 Redundant Databases)
The current Compose configuration spawns 6 separate PostgreSQL instances:
1. `supabase-db` (Port 5432 - Core data & pgvector)
2. `openfga-postgres` (Port 5432 internal - OpenFGA)
3. `infisical-postgres` (Port 5432 internal - Infisical)
4. `lago-postgres` (Port 5432 internal - Lago)
5. `openmeter-postgres` (Port 5432 internal - OpenMeter)
6. `signoz-metastore-postgres-0` (Port 5432 internal - SigNoz)

**Consolidation Action:**
All 5 auxiliary databases can be provisioned as distinct logical databases inside the single `supabase-db` instance using the existing initialization script (`compose/postgres/init-multi-db.sh`):
- `central_openfga`
- `central_infisical`
- `central_lago`
- `central_openmeter`
- `central_signoz`

**Benefit:** Reclaims **~400–600 MiB RAM**, eliminates 5 background daemons, and unifies backup/restore operations.

### 4.2. Cache Consolidation (Eliminating 3 Redundant Redis Instances)
The current configuration spawns:
1. `valkey` (Port 6379 - BSD-3-Clause)
2. `infisical-redis` (redis:7.4.7 - Non-OSI)
3. `openmeter-redis` (redis:7.4.7 - Non-OSI)
4. `lago-redis` (redis:6 - BSD-3-Clause)
5. `dragonfly` (Optional - BSL-1.1)

**Consolidation Action:**
Direct Infisical, OpenMeter, and Lago to connect to the single `valkey` container using separate Redis database numbers (`/0` for Central Intelligence, `/1` for Infisical, `/2` for Lago, `/3` for OpenMeter).

**Benefit:** Eliminates **~60 MiB RAM**, removes Non-OSI Redis 7.4.7 licenses from the core profile, and ensures 100% BSD-3-Clause compliance across all cache services.

---

## 5. Summary Recommendation

By decoupling mandatory capabilities from specific third-party engines and consolidating shared data stores:
1. **The Core Profile RAM Requirement** is reduced from **~8.5 GiB down to ~1.2 GiB**, enabling seamless local execution on standard 8 GB developer machines.
2. **Licensing Compliance** is elevated to 100% OSI-permissive for default deployments (Apache-2.0, MIT, BSD-3-Clause).
3. **Vendor Lock-in is Eliminated:** Central Intelligence can run completely standalone with zero external network calls, while retaining full enterprise interoperability when distributed tools (OpenFGA, Infisical, Temporal, SigNoz) are provisioned.
