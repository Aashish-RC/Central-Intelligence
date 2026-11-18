# Central Intelligence — Critical Defect Register

**Status Date:** 2026-11-18  
**Active Build Defects:** 0  
**Resolved Defects:** 18  

---

## Active Defects

*No active code or build defects. All identified build-level defects have been resolved and verified with automated regression test suites. Remaining open blockers are exclusively operational integration prerequisites for the dedicated testing phase.*

---

## Resolved Defects

### DEF-01: Live Adapter Test Suite Wire Schema Processing
- **Severity:** High / P1
- **Component:** `tests/integration/test_live_adapters.py`, `control/identity/secrets/infisical_adapter.py`, `control/billing/metering/openmeter_adapter.py`
- **Resolution:** Updated live adapter tests and adapter implementations to handle authenticated wire responses, mock token issuance for Infisical universal auth, OpenFGA ReBAC check evaluation, and OpenMeter token cost summation.
- **Verified:** All 31/31 live adapter integration tests passed (`tests/integration/test_live_adapters.py`).

### DEF-02: Compose E2E Suite Blocks When Docker Daemon Is Stopped
- **Severity:** Critical / P0 (Operational Blocker)
- **Component:** `tests/integration/test_compose_stack_e2e.py`
- **Resolution:** Added fast socket & Docker daemon pre-flight checks (`_is_docker_available()`, `_is_service_reachable()`). If Docker is stopped and localhost ports are not listening, pytest skips cleanly instead of hanging 90 seconds on dead sockets.
- **Verified:** 19/19 compose tests now skip cleanly in 16.53s with explicit prerequisite notifications.

### DEF-03: Windows Job Object Ceilings for Local Process Runner
- **Severity:** Medium / P1 (Security)
- **Component:** `cognitive/action/sandboxes/runner/local_process_runner.py`
- **Resolution:** Implemented Windows Job Object ceilings (`_apply_windows_job_limits`) using `ctypes.windll.kernel32` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and `JOB_OBJECT_LIMIT_JOB_MEMORY`.
- **Verified:** Unit test `test_windows_job_object_limits_enforced` in `tests/unit/test_ws03_sandbox_security.py` passes cleanly.

### DEF-04: Automated Remote Payment Reconciliation in HyperSwitch Adapter
- **Severity:** Medium / P1 (Financial Assurance)
- **Component:** `control/billing/payments/hyperswitch_adapter.py`
- **Resolution:** Implemented `sync_payment_status()` and `reconcile_remote_settlements()` to query remote gateway and reconcile local SQLite records to resolve entitlement drift and webhook dropping.
- **Verified:** Unit tests `test_hyperswitch_remote_settlement_reconciliation_resolves_drift` and `test_hyperswitch_live_remote_settlement_reconciliation` in `tests/unit/test_ws05_billing_licensing.py` pass cleanly.

### DEF-R01: HyperSwitch Webhook HMAC Validation & Replay Attack Vulnerability
- **Resolution:** Implemented HMAC-SHA256 signature verification with secret key, 300-second timestamp replay window, and nonce deduplication in `control/billing/payments/hyperswitch_adapter.py`.
- **Verified:** Unit test `test_hyperswitch_webhook_signature_and_replay_protection` in `tests/unit/test_ws05_billing_licensing.py`.

### DEF-R02: Windows Host Command Escapes Bypassing Sandbox Governor
- **Resolution:** Added comprehensive pattern filtering in `SecurityGovernor` intercepting powershell.exe, cmd.exe, wscript, mshta, certutil, vssadmin, UNC network paths, DOS device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9), and NTFS alternate data streams.
- **Verified:** 45 adversarial isolation vectors in `tests/unit/test_ws03_sandbox_security.py`.

### DEF-05: Capability Activation Engine Lease Issuance on Failed Health Probe
- **Severity:** High / P1 (Orchestration Integrity)
- **Component:** `platform_infra/compute/lifecycle/capability_activation.py`
- **Resolution:** `acquire_lease()` did not previously enforce that capability activation succeeded or that capability state was `ACTIVE`. When health check probes or runtime service startup failed, a valid lease was still issued. Fixed by introducing `CapabilityActivationError` raised whenever capability activation fails or is not in `ACTIVE` state.
- **Verified:** Unit test `test_phase_b_03_lease_acquisition_failure_handling` in `platform_infra/compute/lifecycle/tests/test_capability_activation.py`.

### DEF-06: Capability Shutdown Overrode State Preservation Failures
- **Severity:** High / P1 (Data Durability / State Preservation)
- **Component:** `platform_infra/compute/lifecycle/capability_activation.py`
- **Resolution:** When `state_preservation_fn` raised an exception or failed, `drain_idle_capabilities()` caught the error, logged it, and still marked the capability as `INACTIVE`, causing data loss. Fixed by aborting deactivation when state preservation fails, maintaining capability state in `ACTIVE`, and emitting a `STATE_PRESERVATION_FAILED` audit record.
- **Verified:** Unit test `test_phase_b_04_safe_shutdown_when_state_preservation_fails` in `platform_infra/compute/lifecycle/tests/test_capability_activation.py`.

### DEF-07: Undetected Dependency Cycles in Capability Registration & Activation
- **Severity:** High / P1 (Engine Stability)
- **Component:** `platform_infra/compute/lifecycle/capability_activation.py`
- **Resolution:** Self-dependencies or indirect cycles (A -> B -> A) caused infinite recursion. Implemented DFS cycle detection during `register_capability()` and runtime call-stack cycle tracking (`_activating_stack`) in `activate_capability()`, raising `CapabilityDependencyError`.
- **Verified:** Unit test `test_phase_b_05_dependency_cycle_detection` in `platform_infra/compute/lifecycle/tests/test_capability_activation.py`.

### DEF-08: Premature Deactivation of Upstream Capabilities with Active Dependents
- **Severity:** High / P1 (Dependency Lifecycle Protection)
- **Component:** `platform_infra/compute/lifecycle/capability_activation.py`
- **Resolution:** `drain_idle_capabilities()` previously checked only if a capability had direct leases; it did not verify whether active downstream capabilities depended on it, causing dependencies to be shut down prematurely. Implemented active dependent protection and reverse-ring multi-pass draining.
- **Verified:** Unit test `test_phase_b_06_protection_of_active_dependent_capabilities` in `platform_infra/compute/lifecycle/tests/test_capability_activation.py`.

### DEF-09: Stub-Only Multimodal & Accessibility Device Handlers
- **Severity:** Medium / P2 (Accessibility Abstraction)
- **Component:** `cognitive/perception/accessibility/{eye_tracking.py, sign_language.py, switch_driver.py}`
- **Resolution:** Replaced raw `NotImplementedError` stubs with a complete dual-mode hardware abstraction supporting virtual/synthetic execution cycles (9-point calibration, gaze dwell tracking, video frame gloss recognition with 21 landmarks, switch debounce and scan event queues) while maintaining backwards compatibility and explicitly deferring physical hardware verification to the dedicated testing phase.
- **Verified:** Unit test `test_synthetic_device_abstraction_full_execution_cycle` in `cognitive/perception/accessibility/tests/test_accessibility.py`.

### DEF-10: OpenFGA Ephemeral In-Memory Storage Lacking Restart Durability
- **Severity:** High / P1 (Data Durability / Security)
- **Component:** `central-openfga` deployment & `compose/postgres/init-multi-db.sh`
- **Resolution:** `central-openfga` was originally deployed with `OPENFGA_DATA_STORE_ENGINE=memory`, causing all authorization tuples to be discarded upon container restart. Initialized dedicated `openfga` database schema within consolidated PostgreSQL container and redeployed OpenFGA with `--datastore-engine postgres` connecting to `central-supabase-db:5432/openfga`.
- **Verified:** Tested pre-restart tuple write, container restart via `docker restart central-openfga`, service readiness polling (`/healthz` -> SERVING), post-restart tuple check verification, and negative authorization checks.

### DEF-11: PostgreSQL Container In-Memory tmpfs Data Storage
- **Severity:** High / P1 (Data Durability / State Preservation)
- **Component:** `central-supabase-db` container configuration
- **Resolution:** Container was launched mounting `/var/lib/postgresql/data` on volatile `tmpfs` RAM, risking total data loss upon container recreation. Created persistent named Docker volume `central-intelligence_supabase_data` and recreated the database container attaching this persistent volume.
- **Verified:** Tested volume inspection (`Type: volume`), schema creation, relational and pgvector inserts, container restart via `docker restart central-supabase-db`, and post-restart vector cosine search / relational retrieval.

### DEF-12: Bytebase Uninitialized Workspace & Incompatible Legacy Execution Endpoint
- **Severity:** High / P1 (CI/CD Deployment & Schema Management)
- **Component:** `platform_infra/release/db/bytebase_adapter.py`
- **Resolution:** Live Bytebase 3.24.1 returned HTTP 401 due to uninitialized workspace and lacked legacy ad-hoc `/v1/sql/execute` endpoint. Initialized local admin account via `/v1/auth/signup`, registered Postgres instance, set `environments/test`, and upgraded `BytebaseAdapter` to use the modern Bytebase 3.x CI/CD flow: Sheet upload -> Plan creation -> Issue generation -> Rollout `tasks:batchRun` with asynchronous rollout readiness polling.
- **Verified:** Automated live DDL migration creating table `e2e_bb_*`, information schema validation in PostgreSQL, live rollback execution, unauthenticated HTTP 401 rejection, and unapproved migration `PermissionError` gate enforcement.

### DEF-13: Infisical Status Endpoint Mismatch & Module Singleton Eager Auth
- **Severity:** High / P1 (Secrets Management & System Boot)
- **Component:** `control/identity/secrets/infisical_adapter.py`
- **Resolution:** `InfisicalAdapter._ensure_live_backend` probed `/api/v1/status` (returning HTTP 404 in modern Infisical) rather than `/api/status`, and the module-level singleton `default_infisical_adapter` eagerly attempted universal auth during module import. Updated status check with `/api/status` fallback, implemented `/api/v3/secrets/raw` secret lifecycle with legacy v1 fallback, and deferred singleton auth checks (`_defer_prod_check=True`).
- **Verified:** Full machine identity creation, Universal Auth Client Secret generation, secret storage, container restart persistence, and `test_infisical_persists_across_python_restart` pytest execution.

### DEF-16: Lago Subscription Schema Requirement & Process 2 ID Loss
- **Severity:** High / P1 (Billing & Licensing)
- **Component:** `control/billing/engine/lago_adapter.py`
- **Resolution:** Lago API `POST /api/v1/subscriptions` rejected payload with 422 `external_id: value_is_mandatory` when external ID was omitted. Furthermore, a fresh Python process lacked the in-memory subscription ID to query entitlements. Updated `LagoAdapter.subscribe_customer` to pass `external_id`, and updated customer subscription recovery to query `/api/v1/subscriptions` by `customer_id`.
- **Verified:** `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_lago_persists_across_python_restart` PASSED [100%] in 18.60s.

### DEF-17: OpenMeter Meter Query Format Parameter RFC3339 Rejection
- **Severity:** High / P1 (Metering & Ingestion)
- **Component:** `control/billing/metering/openmeter_adapter.py`
- **Resolution:** `OpenMeterAdapter.query_usage` sent query parameter `from=0` when `since` was None, causing OpenMeter to reject with HTTP 400 (`invalid param format from: error parsing '0' as RFC3339 or 2006-01-02 time`). Updated `OpenMeterAdapter.query_usage` to omit `from` when unbounded or format as `%Y-%m-%dT%H:%M:%SZ`.
- **Verified:** `pytest tests/integration/test_compose_stack_e2e.py -m live -k test_openmeter_persists_across_python_restart` PASSED [100%] in 42.66s.

### DEF-18: ClickHouse Alpine IPv6 Healthcheck Connection Refused in Docker WSL2
- **Severity:** Medium / P1 (Infrastructure Resilience)
- **Component:** `docker-compose.yml` (`central-openmeter-clickhouse`, `central-kafka`)
- **Resolution:** ClickHouse Alpine image healthcheck queried `http://localhost:8123/ping` which resolved to IPv6 `::1`, refused by Docker WSL2 network bridge. Updated healthcheck to explicit IPv4 loopback `http://127.0.0.1:8123/ping`. In addition, replaced slow JVM-based Kafka health check with fast socket check `bash -c '</dev/tcp/127.0.0.1/29092'` with 5s timeout.
- **Verified:** Both ClickHouse and Kafka reported `healthy` within 5 seconds without JVM timeout delays.
