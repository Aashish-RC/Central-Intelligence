# CENTRAL INTELLIGENCE — RISK REGISTER & THREAT MATRIX

**Document ID:** `AUDIT-DELIVERABLE-09`  
**Classification:** STRICT AUDIT / RESTRICTED  
**Baseline Git Commit:** `138b95b` | **CI Run:** `43480953326`  
**Status:** COMPLETE / CANONICAL  
**Auditor:** Principal Software Architect, Senior Security Auditor & QA Lead  

---

## 1. Executive Risk Overview & Assessment Methodology

This Risk Register consolidates all operational, security, compliance, architectural, and financial risks identified during the 19-layer audit of the Central Intelligence platform. Each risk is evaluated under two conditions:
1. **Current Inherent State (Pre-Remediation):** The repository state at commit `138b95b`.
2. **Projected Residual State (Post-Remediation):** Assuming the execution of Milestones M1 through M4 as detailed in [08_PRIORITIZED_COMPLETION_ROADMAP.md](file:///workspaces/Central-Intelligence/audit-output/08_PRIORITIZED_COMPLETION_ROADMAP.md).

### 1.1 Risk Scoring Formula

Risks are quantified using the standard risk matrix formula:

$$\text{Risk Score} (R) = \text{Likelihood} (L) \times \text{Impact} (I)$$

Where:
* **Likelihood ($L \in [1, 5]$):**
  * `1` — Rare: Requires improbable sequence of events.
  * `2` — Unlikely: Possible in edge cases or during abnormal operational stress.
  * `3` — Moderate: Expected to occur periodically under normal operations.
  * `4` — Likely: Will occur frequently in production without deliberate intervention.
  * `5` — Almost Certain: Guaranteed to occur immediately upon deployment or container restart.
* **Impact ($I \in [1, 5]$):**
  * `1` — Negligible: Cosmetic issue, log noise, minor developer friction.
  * `2` — Minor: Degraded non-critical feature, fallback available without data loss.
  * `3` — Moderate: Partial service disruption, transient errors, performance degradation.
  * `4` — Major: Significant data loss, unauthorized access, financial miscalculation, durable workflow stall.
  * `5` — Catastrophic: Total platform amnesia, complete bypass of security gates, unauthorized financial charge, AGPL contamination, or systemic unrecoverable data corruption.

### 1.2 Severity Classification Bands

| Score Range | Severity Band | Action Required | Release Gate Policy |
| :--- | :--- | :--- | :--- |
| **20 – 25** | **CRITICAL (P0)** | Immediate remediation required before any external deployment. | **HARD BLOCKER (NO-GO)** |
| **12 – 19** | **HIGH (P1)** | Remediation required before beta/staging release. | **CONDITIONAL BLOCKER** |
| **6 – 11** | **MEDIUM (P2)** | Remediation scheduled for subsequent maintenance milestone. | Acceptable with sign-off |
| **1 – 5** | **LOW (P3)** | Technical debt / minor backlog item. | Acceptable |

---

## 2. Master Risk Matrix

| Risk ID | Category | Risk Description | $L$ | $I$ | Score | Band | Status | Primary Owner |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **R-01** | Security / Governance | **Production Guard Bypass via Variable Name Mismatch** (`ENV` vs `ENVIRONMENT`) | 5 | 5 | **25** | **CRITICAL** | `[VERIFIED]` | Security Lead |
| **R-02** | Security / Identity | **Ephemeral Vault Storage — Total Secret Loss on Container Restart** (`InfisicalAdapter`) | 5 | 5 | **25** | **CRITICAL** | `[VERIFIED]` | Platform Infra |
| **R-03** | Security / AuthZ | **Zanzibar ReBAC In-Memory Amnesia — Tenant & Permission Wipe** (`OpenFGAAdapter`) | 5 | 5 | **25** | **CRITICAL** | `[VERIFIED]` | Platform Infra |
| **R-04** | Security / AuthN | **In-Memory Identity Store — User & Credential Amnesia** (`KeycloakAdapter`) | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | Platform Infra |
| **R-05** | Financial / Billing | **Silent Payment Processing Bypass & Error Swallowing** (`HyperswitchAdapter`) | 5 | 5 | **25** | **CRITICAL** | `[VERIFIED]` | Billing Lead |
| **R-06** | Financial / Billing | **In-Memory Metering & Subscription Billing Quota Reset** (`Lago` & `OpenMeter`) | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | Billing Lead |
| **R-07** | Observability | **Telemetry Black Hole — Dead Tracing & Unexported Spans** (`SigNozAdapter`) | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | SRE / Ops |
| **R-08** | Data / Persistence | **PostgreSQL/pgvector/AGE Bypass — In-Memory Dictionary Storage** (`SupabaseAdapter`) | 5 | 5 | **25** | **CRITICAL** | `[VERIFIED]` | Data Architect |
| **R-09** | Quality / CI | **"Simulated CI Paradox" — Passing Test Suite Masking Broken Production** | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | QA Lead |
| **R-10** | Governance / Safety | **Dead Imports of Production Safety Guard Across 19 Adapters** | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | Core Arch |
| **R-11** | Supply Chain / Ops | **Missing Core Dependencies in `requirements.lock`** (`psycopg2`, `paddleocr`, etc.) | 5 | 4 | **20** | **CRITICAL** | `[VERIFIED]` | Release Eng |
| **R-12** | Orchestration | **Temporal Server Bypass — Local File Checkpoints with Race Conditions** | 4 | 4 | **16** | **HIGH** | `[VERIFIED]` | Workflow Lead |
| **R-13** | Release / CI/CD | **Kamal Deployment & Bytebase Migration Phantom Execution** | 4 | 4 | **16** | **HIGH** | `[VERIFIED]` | Release Eng |
| **R-14** | Architecture | **Gateway-to-Runtime Disconnection** (TypeScript Gateway vs Python Runtime) | 4 | 4 | **16** | **HIGH** | `[VERIFIED]` | Core Arch |
| **R-15** | Perception / Media | **Media Generation & Voice Synthesis Stubbed Mocks** (PIL & string formatting) | 4 | 3 | **12** | **HIGH** | `[VERIFIED]` | Perception Lead |
| **R-16** | Action / Physical | **Physical & Accessibility Drivers Raising `NotImplementedError`** | 4 | 3 | **12** | **HIGH** | `[VERIFIED]` | Action Lead |
| **R-17** | Security / Sandbox | **Docker Daemon Socket Mount in Tool Execution Sandbox** | 3 | 4 | **12** | **HIGH** | `[VERIFIED]` | Security Lead |
| **R-18** | Data / Vector | **pgvector Cosine Distance Semantic Discrepancy in In-Memory Math** | 4 | 3 | **12** | **HIGH** | `[INFERRED]` | Data Architect |
| **R-19** | Multi-Tenancy | **Cross-Tenant Collision Risk via Shared Dictionary Keys in Adapters** | 3 | 4 | **12** | **HIGH** | `[INFERRED]` | Security Lead |
| **R-20** | Operations | **Operational Runbook & Documentation Drift** (`docs/DEPLOYMENT.md`) | 4 | 2 | **8** | **MEDIUM** | `[VERIFIED]` | Docs / Tech Writer |

---

## 3. Detailed Risk Cards

### R-01: Production Guard Bypass via Variable Name Mismatch
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/safety/production_guard.py#L30-L32](file:///workspaces/Central-Intelligence/control/safety/production_guard.py#L30-L32)
  * [docs/DEPLOYMENT.md#L33](file:///workspaces/Central-Intelligence/docs/DEPLOYMENT.md#L33)
  * [docs/SECURITY_REVIEW.md#L51](file:///workspaces/Central-Intelligence/docs/SECURITY_REVIEW.md#L51)
* **Root Cause:**
  `production_guard.py` checks `os.getenv("ENVIRONMENT") == "production"`. However, operational deployment documentation instructs operations engineers to set `ENV=production`. Because `ENVIRONMENT` is left unset, `is_production()` evaluates to `False`.
* **Failure Scenario:**
  A production container deployed according to the official documentation boots up. The mock adapters detect `is_production() == False`. Mock adapters (Infisical, Supabase, Keycloak, Hyperswitch) run in RAM instead of halting with `RuntimeError`. Financial transactions and credentials operate entirely in memory without raising an alarm.
* **Business Impact:**
  Complete failure of safety gates. Untested in-memory mock adapters run silently in live customer-facing environments. Total data loss upon process shutdown.
* **Remediation Plan:**
  Refactor `is_production()` to check both `ENVIRONMENT` and `ENV`, matching `"production"`, `"prod"`, and `"live"`. Mandate a fatal error if either variable is set to production while adapters are running in mock mode.

---

### R-02: Ephemeral Vault Storage — Total Secret Loss on Container Restart
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/identity/secrets/infisical_adapter.py#L22-L58](file:///workspaces/Central-Intelligence/control/identity/secrets/infisical_adapter.py#L22-L58)
* **Root Cause:**
  `InfisicalAdapter` stores all API keys, tenant credentials, database passwords, and OAuth client secrets in `self._vault = {}` (in-memory Python dictionary). It does not initiate HTTP/REST or SDK connections to the Infisical service defined in `docker-compose.yml` (`infisical:8083`).
* **Failure Scenario:**
  An enterprise tenant configures BYOK API keys (OpenAI, Anthropic, AWS). A Kubernetes pod autoscaling event, rolling update, or node reboot restarts the Central Intelligence container. `self._vault` is wiped. All agent requests fail instantly with missing key errors. If an attacker gains local memory access, secrets are stored unencrypted in heap memory.
* **Business Impact:**
  Catastrophic tenant disruption, operational downtime, potential memory-scraping vulnerability.
* **Remediation Plan:**
  Implement live `httpx.AsyncClient` calls to `http://infisical:8083/api/v1/secrets` using Infisical Machine Identity credentials. Remove fallback dictionary storage when `ENV=production`.

---

### R-03: Zanzibar ReBAC In-Memory Amnesia — Tenant & Permission Wipe
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/identity/openfga_adapter.py#L25-L72](file:///workspaces/Central-Intelligence/control/identity/openfga_adapter.py#L25-L72)
* **Root Cause:**
  `OpenFGAAdapter` stores Zanzibar relationship tuples (`user`, `relation`, `object`) in `self._tuples = set()`. It never connects to OpenFGA Server (`openfga:8081`).
* **Failure Scenario:**
  Enterprise authorization rules (e.g., `user:alice is viewer of workspace:acme`) are written. Upon process restart, `self._tuples` resets to empty. When `check_permission()` is called, all authorization queries return `DENIED` (or default permissive if improperly mocked), locking every user out of their resources.
* **Business Impact:**
  Total service denial for all users or privilege escalation across organizational boundaries.
* **Remediation Plan:**
  Wire the official `openfga-sdk` async client to connect to `OPENFGA_API_URL` (`http://openfga:8081`). Enforce schema model synchronization on service startup.

---

### R-04: In-Memory Identity Store — User & Credential Amnesia
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/identity/keycloak_adapter.py#L20-L80](file:///workspaces/Central-Intelligence/control/identity/keycloak_adapter.py#L20-L80)
* **Root Cause:**
  `KeycloakAdapter` manages user accounts, password hashes, and session tokens within an in-memory dictionary. It makes no OIDC/OAuth2 calls to Keycloak (`keycloak:8085`).
* **Failure Scenario:**
  Users register and authenticate. Upon container restart, all user identities vanish. JWT tokens previously issued cannot be verified against the Keycloak JWKS endpoint.
* **Business Impact:**
  User authentication lockouts, inability to maintain persistent sessions across multi-pod deployments.
* **Remediation Plan:**
  Integrate Keycloak Admin REST API and OIDC discovery endpoints (`/realms/master/.well-known/openid-configuration`). Validate JWT tokens via public key cryptography rather than internal dictionary lookups.

---

### R-05: Silent Payment Processing Bypass & Error Swallowing
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/billing/payments/hyperswitch_adapter.py#L157-L159](file:///workspaces/Central-Intelligence/control/billing/payments/hyperswitch_adapter.py#L157-L159)
* **Root Cause:**
  In `create_payment()`, when live HTTP communication with Hyperswitch (`hyperswitch:8080`) throws any exception, the adapter executes `except Exception: pass` and falls back to generating a fake `mock_pay_12345` transaction with status `succeeded`.
* **Failure Scenario:**
  A customer initiates a payment. The network between the Central Intelligence backend and Hyperswitch experiences a transient timeout or configuration error. The exception is swallowed silently. The platform records the transaction as `succeeded`, grants the user enterprise credits, and fulfills expensive LLM workloads without collecting payment.
* **Business Impact:**
  Massive direct financial loss, unfunded API consumption, compliance violations under PCI-DSS and financial accounting standards.
* **Remediation Plan:**
  Remove the silent `pass` block. Throw `PaymentGatewayError` with proper transaction rollback. Never record a transaction as successful without a cryptographic webhook signature or 200 OK receipt from the payment processor.

---

### R-06: In-Memory Metering & Subscription Billing Quota Reset
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/billing/engine/lago_adapter.py#L19-L85](file:///workspaces/Central-Intelligence/control/billing/engine/lago_adapter.py#L19-L85)
  * [control/billing/metering/openmeter_adapter.py#L22-L68](file:///workspaces/Central-Intelligence/control/billing/metering/openmeter_adapter.py#L22-L68)
* **Root Cause:**
  `LagoAdapter` imports `httpx` on line 19 but never uses it. It calculates subscription quotas in Python RAM. `OpenMeterAdapter` stores usage events in a local Python list.
* **Failure Scenario:**
  A tenant exhausts their free 10,000 token limit. The container restarts. Token usage counters reset to zero. The user can indefinitely consume LLM compute by triggering container recycles or exploiting horizontal pod auto-scaling.
* **Business Impact:**
  Unbounded resource abuse, inability to bill customers accurately, cloud provider invoice shock.
* **Remediation Plan:**
  Implement live HTTP event ingestion to OpenMeter (`openmeter:8888/api/v1/events`) and Lago API (`lago-api:3000`). Enforce hard quota checks querying durable storage.

---

### R-07: Telemetry Black Hole — Dead Tracing & Unexported Spans
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/observability/signoz/signoz_adapter.py#L18-L75](file:///workspaces/Central-Intelligence/control/observability/signoz/signoz_adapter.py#L18-L75)
* **Root Cause:**
  Imports `fail_closed_in_production` and `httpx` but never executes either. Span creation simply appends Python dictionaries to `self._spans = []`. No OTLP (OpenTelemetry Protocol) exporter is initialized.
* **Failure Scenario:**
  A critical production crash, security breach, or slow query occurs. SRE engineers open the SigNoz dashboard (`:3301`). The dashboard is completely empty. No traces, logs, or metrics exist to debug or reconstruct the incident.
* **Business Impact:**
  Zero production visibility, prolonged Mean Time to Resolution (MTTR), inability to fulfill SOC 2 / ISO 27001 observability requirements.
* **Remediation Plan:**
  Wire the standard OpenTelemetry SDK (`opentelemetry-exporter-otlp-proto-grpc`) to export spans and metrics to `signoz-otel-collector:4317`.

---

### R-08: PostgreSQL/pgvector/AGE Bypass — In-Memory Dictionary Storage
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [platform_infra/data/supabase/supabase_adapter.py#L25-L110](file:///workspaces/Central-Intelligence/control/../platform_infra/data/supabase/supabase_adapter.py#L25-L110)
* **Root Cause:**
  `SupabaseAdapter` simulates PostgreSQL relational tables, pgvector cosine similarity search, and Apache AGE graph queries using in-memory Python dictionaries and `math.sqrt`. It does not use `psycopg2`, `asyncpg`, or `postgrest-py`.
* **Failure Scenario:**
  Knowledge graphs, user profiles, conversation memories, and semantic embeddings are saved. The application process restarts. The database is blank. Any data previously stored is permanently lost.
* **Business Impact:**
  Total loss of application state, corruption of user memory, catastrophic platform failure.
* **Remediation Plan:**
  Replace mock dictionary operations with `asyncpg` or `SQLAlchemy` async connection pool pointed to PostgreSQL/Supabase (`postgres:5432`). Execute actual SQL DDL and pgvector queries.

---

### R-09: "Simulated CI Paradox" — Passing Test Suite Masking Broken Production
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [.github/workflows/ci.yml#L1-L150](file:///workspaces/Central-Intelligence/.github/workflows/ci.yml#L1-L150)
  * [tests/unit/test_production_guard.py](file:///workspaces/Central-Intelligence/tests/unit/test_production_guard.py)
* **Root Cause:**
  All 2,615 unit and integration tests run against mock adapters. Because mock adapters do not connect to external network sockets or require real services, CI passes in 3.5 minutes. Not a single CI job validates that adapters can connect to live Docker services.
* **Failure Scenario:**
  Leadership approves a production release based on "100% green CI run 43480953326". Upon deployment to live infrastructure with real database and vault endpoints, the application either crashes on startup due to missing dependencies or silently runs mock adapters without persisting any data.
* **Business Impact:**
  False sense of security, release failure, emergency rollbacks, executive reputational damage.
* **Remediation Plan:**
  Create a dedicated `ci-live.yml` workflow that spins up real container services (PostgreSQL, Redis, OpenFGA, Infisical) using GitHub Actions service containers and executes integration tests with `ADAPTER_MODE=live`.

---

### R-10: Dead Imports of Production Safety Guard Across 19 Adapters
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * 19 adapter files across `control/`, `cognitive/`, and `platform_infra/` (see [05_SECURITY_AND_GOVERNANCE.md](file:///workspaces/Central-Intelligence/audit-output/05_SECURITY_AND_GOVERNANCE.md#31-dead-import-analysis) for complete list).
* **Root Cause:**
  `from control.safety.production_guard import fail_closed_in_production` is imported at the top of 19 adapter files, but the function is never invoked in `__init__()`, `connect()`, or any operational method.
* **Failure Scenario:**
  An engineer expects that mock adapters will automatically crash if instantiated in production. In reality, the imported guard is completely dead code. The mock adapter initializes and operates without objection.
* **Business Impact:**
  Safety guard bypass across 57.5% of the platform's infrastructure adapters.
* **Remediation Plan:**
  Add `fail_closed_in_production(self.__class__.__name__)` inside `__init__()` of every mock adapter or eliminate mock adapters entirely from the production image.

---

### R-11: Missing Core Dependencies in `requirements.lock`
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [requirements.lock](file:///workspaces/Central-Intelligence/requirements.lock)
  * [pyproject.toml#L40-L75](file:///workspaces/Central-Intelligence/pyproject.toml#L40-L75)
* **Root Cause:**
  Critical live libraries required by adapters—specifically `psycopg2` / `asyncpg` (PostgreSQL), `paddleocr` (OCR), `faster-whisper` (ASR), and `confluent-kafka` (Streaming)—are completely omitted from `requirements.lock`.
* **Failure Scenario:**
  An operator switches `ADAPTER_MODE=live` and restarts the service. The service immediately crashes during module import with `ModuleNotFoundError: No module named 'faster_whisper'`.
* **Business Impact:**
  Immediate container crash-loop backoff on live deployment.
* **Remediation Plan:**
  Audit all adapter import statements. Update `pyproject.toml` and run `pip-compile` to freeze all required production dependencies into `requirements.lock`.

---

### R-12: Durable Workflow Bypass — Local File Checkpoints with Race Conditions
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [control/orchestration/workflow_builder/runtime/temporal_adapter.py#L30-L78](file:///workspaces/Central-Intelligence/control/orchestration/workflow_builder/runtime/temporal_adapter.py#L30-L78)
* **Root Cause:**
  `TemporalAdapter` persists workflow state as raw JSON files in a local directory (`./.temporal_checkpoints/<workflow_id>.json`). It does not communicate with Temporal Server (`temporal:7233`).
* **Failure Scenario:**
  In a multi-pod Kubernetes cluster or multi-container environment, workflow tasks executed by pod A write checkpoints to pod A's ephemeral local disk. Pod B receives the next step of the workflow, checks its own local disk, finds no checkpoint, and fails or restarts the workflow from the beginning. Additionally, concurrent writes to the same local JSON file suffer from file corruption without flock locking.
* **Business Impact:**
  Loss of distributed workflow durability, non-deterministic agent executions, split-brain workflow state.
* **Remediation Plan:**
  Implement the official Temporal Python SDK (`temporalio.client.Client`) connecting to `temporal:7233`.

---

### R-13: Kamal Deployment & Bytebase Migration Phantom Execution
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [platform_infra/release/ci/kamal_adapter.py#L20-L55](file:///workspaces/Central-Intelligence/platform_infra/release/ci/kamal_adapter.py#L20-L55)
  * [platform_infra/release/db/bytebase_adapter.py#L22-L60](file:///workspaces/Central-Intelligence/platform_infra/release/db/bytebase_adapter.py#L22-L60)
* **Root Cause:**
  `KamalAdapter` records deployment commands in a Python list without calling the `kamal` CLI or Docker daemon. `BytebaseAdapter` splits SQL strings on semicolons in memory without connecting to Bytebase API (`:8080`) or executing schema migrations.
* **Failure Scenario:**
  An operator triggers a deployment or database migration via the Central Intelligence release plane. The system reports `STATUS: SUCCESS` in under 10 milliseconds. In reality, zero containers were deployed, and zero database schema migrations were applied. The old code and outdated database schema remain running, leading to silent schema mismatch errors.
* **Business Impact:**
  False deployment confirmations, database schema desynchronization, release roll-forward failures.
* **Remediation Plan:**
  Integrate real Bytebase REST API client for SQL migration rollouts. Implement real deployment drivers or remove release automation if delegating to external CI/CD pipelines (e.g. GitHub Actions).

---

### R-14: Gateway-to-Runtime Disconnection (TypeScript vs Python)
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [cognitive/reasoning/](file:///workspaces/Central-Intelligence/cognitive/reasoning/) (TypeScript, ~23,000 LOC)
  * [control/orchestration/agent_core/](file:///workspaces/Central-Intelligence/control/orchestration/agent_core/) (Python)
* **Root Cause:**
  The AI Model Gateway is a standalone Node.js/TypeScript service with extensive routing, caching, and rate-limiting features. The Python agent runtime communicates with LLM providers directly via Python SDKs (`openai`, `anthropic`, `google-genai`), bypassing the gateway entirely.
* **Failure Scenario:**
  Advanced features implemented in the TypeScript gateway (CEL-based model routing, token-bucket rate limits, token cost tracking, session affinity, MoA fusion) are never utilized during agent execution.
* **Business Impact:**
  Wasted architectural investment, unthrottled LLM spending, lack of unified model routing across language boundaries.
* **Remediation Plan:**
  Configure Python LLM clients (`openai.base_url`, etc.) to route all outbound model inference through `http://model-gateway:3000/v1` as an OpenAI-compatible reverse proxy.

---

### R-15: Media Generation & Voice Synthesis Stubbed Mocks
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [perception/vision/sd_adapter.py#L25-L60](file:///workspaces/Central-Intelligence/perception/vision/sd_adapter.py#L25-L60)
  * [action/voice/tts_adapter.py#L20-L55](file:///workspaces/Central-Intelligence/action/voice/tts_adapter.py#L20-L55)
* **Root Cause:**
  `sd_adapter.py` generates 512x512 blank RGB images with text using `PIL.ImageDraw`. `tts_adapter.py` outputs dummy byte arrays or invokes mock audio formatters.
* **Failure Scenario:**
  User requests multimodal agent actions (generating image assets or voice responses). The platform returns static dummy files or placeholder images instead of genuine synthetic media.
* **Business Impact:**
  User dissatisfaction, inability to deliver promised multimodal capabilities.
* **Remediation Plan:**
  Connect `sd_adapter.py` to a real Stable Diffusion / Flux API endpoint or local ComfyUI instance. Wire `tts_adapter.py` to ElevenLabs or open-source Coqui/XTTS server.

---

### R-16: Physical & Accessibility Drivers Raising `NotImplementedError`
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [action/physical/robotics_adapter.py#L30-L45](file:///workspaces/Central-Intelligence/action/physical/robotics_adapter.py#L30-L45)
  * [action/accessibility/screen_reader_adapter.py#L25-L40](file:///workspaces/Central-Intelligence/action/accessibility/screen_reader_adapter.py#L25-L40)
* **Root Cause:**
  Methods in robotics and accessibility drivers contain explicit `raise NotImplementedError("Hardware interface not connected")`.
* **Failure Scenario:**
  An agent attempts to execute an embodied action or screen reader accessibility narration. The thread raises an unhandled exception and aborts.
* **Business Impact:**
  Layer 15 and Layer 16 are functionally unusable for physical or assistive automation.
* **Remediation Plan:**
  Clearly document physical interfaces as experimental/dormant. Wrap hardware calls in safe feature-flag checks that gracefully report capability unavailability to the agent planner.

---

### R-17: Docker Daemon Socket Mount in Tool Execution Sandbox
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [action/sandbox/local_docker_adapter.py#L35-L80](file:///workspaces/Central-Intelligence/action/sandbox/local_docker_adapter.py#L35-L80)
  * [docker-compose.yml#L180-L195](file:///workspaces/Central-Intelligence/docker-compose.yml#L180-L195)
* **Root Cause:**
  The tool execution sandbox mounts `/var/run/docker.sock` to allow agent code to spawn ephemeral worker containers.
* **Failure Scenario:**
  An autonomous agent generates or executes untrusted Python code that connects to `/var/run/docker.sock`. By issuing standard Docker API commands, the container escapes its sandbox, mounts the host root filesystem (`/`), and gains root control over the host VM.
* **Business Impact:**
  Full host compromise, lateral movement across cloud infrastructure, severe security breach.
* **Remediation Plan:**
  Deprecate Docker socket mounting. Migrate tool execution to rootless gVisor (`runsc`), Firecracker microVMs, or WebAssembly (Wasmtime) sandboxes.

---

### R-18: pgvector Cosine Distance Semantic Discrepancy in In-Memory Math
* **Classification:** `[INFERRED]`
* **Affected Files:**
  * [platform_infra/data/supabase/supabase_adapter.py#L85-L105](file:///workspaces/Central-Intelligence/control/../platform_infra/data/supabase/supabase_adapter.py#L85-L105)
* **Root Cause:**
  The in-memory cosine similarity implementation uses standard Python floating-point math without normalizing zero-vectors or handling dimensional truncation, differing from PostgreSQL `pgvector` HNSW index distance calculations.
* **Failure Scenario:**
  Semantic search queries that pass in test suites return different top-$k$ nearest neighbors when switched to real pgvector due to indexing approximation and quantization differences.
* **Business Impact:**
  Retrieval quality degradation, non-reproducible RAG responses.
* **Remediation Plan:**
  Standardize vector retrieval benchmarking against real pgvector HNSW indices with identical distance metrics (`<=>` cosine vs `<+>` L1 vs `<->` L2).

---

### R-19: Cross-Tenant Collision Risk via Shared Dictionary Keys in Adapters
* **Classification:** `[INFERRED]`
* **Affected Files:**
  * [control/context/memory/](file:///workspaces/Central-Intelligence/control/context/memory/)
  * [control/identity/openfga_adapter.py#L30](file:///workspaces/Central-Intelligence/control/identity/openfga_adapter.py#L30)
* **Root Cause:**
  Multiple in-memory adapters store objects keyed by simple IDs (e.g. `doc_123` or `user_456`) without strictly prefixing keys with `tenant_id`.
* **Failure Scenario:**
  Tenant A and Tenant B both create a resource with ID `default` or `config`. In mock/in-memory mode, Tenant B overwrites or reads Tenant A's resource.
* **Business Impact:**
  Multi-tenant data bleed, unauthorized data disclosure.
* **Remediation Plan:**
  Enforce composite primary keys (`tenant_id:resource_id`) across all data stores and access layers.

---

### R-20: Operational Runbook & Documentation Drift
* **Classification:** `[VERIFIED]`
* **Affected Files:**
  * [docs/DEPLOYMENT.md](file:///workspaces/Central-Intelligence/docs/DEPLOYMENT.md)
  * [docs/RELEASE_CHECKLIST.md](file:///workspaces/Central-Intelligence/docs/RELEASE_CHECKLIST.md)
* **Root Cause:**
  Documentation refers to non-existent scripts, obsolete configuration flags, and contradictory environment variable specifications (`ENV` vs `ENVIRONMENT`).
* **Failure Scenario:**
  A new DevOps engineer attempts to deploy the platform following `docs/DEPLOYMENT.md` and encounters immediate failures due to missing parameters and incorrect port mappings.
* **Business Impact:**
  Extended onboarding time, high operational toil, deployment misconfigurations.
* **Remediation Plan:**
  Perform a complete documentation refresh aligning all docs with actual container and codebase configurations. Add automated doc testing / markdown linting to CI.

---

## 4. Inherent vs. Residual Risk Heatmap

### 4.1 Inherent Risk Matrix (Current Repository State: Commit `138b95b`)

| Impact \ Likelihood | 1 (Rare) | 2 (Unlikely) | 3 (Moderate) | 4 (Likely) | 5 (Almost Certain) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **5 (Catastrophic)** | — | — | — | — | **R-01, R-02, R-03, R-05, R-08** |
| **4 (Major)** | — | — | **R-17, R-19** | **R-12, R-13, R-14** | **R-04, R-06, R-07, R-09, R-10, R-11** |
| **3 (Moderate)** | — | — | — | **R-15, R-16, R-18** | — |
| **2 (Minor)** | — | — | — | **R-20** | — |
| **1 (Negligible)** | — | — | — | — | — |

* **Total Critical Risks (Score 20–25):** 11
* **Total High Risks (Score 12–19):** 8
* **Total Medium Risks (Score 6–11):** 1
* **Inherent Platform Posture:** **UNACCEPTABLE FOR PRODUCTION (RELEASE BLOCKED)**

---

### 4.2 Projected Residual Risk Matrix (Post-Remediation: Milestones M1–M4)

| Impact \ Likelihood | 1 (Rare) | 2 (Unlikely) | 3 (Moderate) | 4 (Likely) | 5 (Almost Certain) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **5 (Catastrophic)** | — | — | — | — | — |
| **4 (Major)** | **R-01, R-02, R-03, R-05** | **R-08, R-17** | — | — | — |
| **3 (Moderate)** | **R-04, R-06, R-07** | **R-12, R-13, R-14** | — | — | — |
| **2 (Minor)** | **R-09, R-10, R-11** | **R-15, R-16, R-18, R-19** | — | — | — |
| **1 (Negligible)** | **R-20** | — | — | — | — |

* **Projected Critical Risks:** 0
* **Projected High Risks:** 2 (R-08, R-17 mitigated to acceptable residual levels under controlled VPC/gVisor sandboxing)
* **Projected Medium/Low Risks:** 18
* **Residual Platform Posture:** **PRODUCTION-READY**

---

## 5. Risk Ownership & Governance Sign-Off Requirements

To formally transition any risk from **Active** to **Mitigated**, the following sign-offs are strictly required:

| Risk Category | Primary Required Sign-Off | Secondary Required Sign-Off | Verification Artifact |
| :--- | :--- | :--- | :--- |
| **Security & Auth (R-01..04, R-10, R-17)** | Security Lead (`SEC-SIGN`) | Core Architect (`ARCH-SIGN`) | Live penetration test report & container scan |
| **Financial & Billing (R-05, R-06)** | Billing Lead (`BILL-SIGN`) | Compliance Officer (`COMP-SIGN`) | Live webhook test trace & reconciliation log |
| **Data & Persistence (R-02, R-03, R-08)** | Data Architect (`DATA-SIGN`) | SRE Lead (`SRE-SIGN`) | 24-hour persistence & restart verification run |
| **Quality & Supply Chain (R-09, R-11)** | QA Lead (`QA-SIGN`) | Release Engineer (`REL-SIGN`) | Live CI pipeline run on GitHub Actions |
| **Orchestration & Gateway (R-12..14)** | Core Architect (`ARCH-SIGN`) | Platform Infra Lead (`INFRA-SIGN`) | E2E distributed trace from Python to Gateway |
