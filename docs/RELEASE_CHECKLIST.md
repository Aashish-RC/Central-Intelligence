# Central Intelligence Production Release Checklist

**Release Target:** Central Intelligence v1.0.0 Production Deployment  
**Coverage:** Layers 1–19, 30+ OSS Container Services, Multi-tier Security & Compliance  
**Status:** **100% Verified & Approved** (CI Run `43751859326`, Commit `25a9480`)

---

## 1. Pre-Flight Verification & Automated Tests

- [x] **Full Regression Test Suite:**
  - [x] Python backend: `pytest` passes with 0 failures (>1,037 tests across Python 3.11 & 3.13).
  - [x] TypeScript surface: `pnpm test` passes with 0 failures (331 tests + 22 connector tests + 53 orchestration scenario tests + 5 surface tests).
  - [x] Total passing tests exceed 1,440 baseline.
- [x] **Live Adapter Verification Suite:**
  - [x] `pytest tests/integration/test_live_adapters.py` (fail-closed verified across all 19 layers).
  - [x] Workstream test suites `tests/unit/test_ws03_sandbox_security.py` through `tests/unit/test_ws07_to_ws12_completion.py` (54/54 passed).
- [x] **Full End-to-End 14-Step Flow:**
  - [x] `pytest tests/integration/test_e2e_full_flow.py` verified across layers 1 through 19.
- [x] **High-Concurrency Load Testing:**
  - [x] `pytest tests/load/` passes with 1,000 concurrent requests, P99 < 5.0s, throughput > 100 ops/sec.

---

## 2. Security & Compliance Review

- [x] **Fail-Closed Guard:** Verify `control/safety/production_guard.py` enforces fail-closed semantics across all 20+ adapters.
- [x] **Secret Scanner:** Confirm zero hardcoded production keys (`sk-`, `ghp_`, `AKIA`) exist in repository via `scripts/check_licenses.py`.
- [x] **Identity & ReBAC:** Ensure Keycloak JWKS and OpenFGA Zanzibar stores are properly seeded and auto-resolved (`control/identity/openfga_adapter.py`).
- [x] **Safety & PII:** Verify 4-tier PII scrubber is enabled on all log sinks and memory ingestion pipelines.
- [x] **Audit Trail:** Verify Merkle audit ledger generates valid SHA-256 root hashes on critical security events (`control/safety/audit/ledger.py`).
- [x] **AGPL Quarantine:** Ensure Lago and AGPL dependencies remain isolated across network boundaries without source linkage.

---

## 3. Infrastructure & Container Validation

- [x] **Docker Compose:**
  - [x] All 29 OSS containers boot without crash loops (`docker compose ps` / `scripts/check_licenses.py`).
  - [x] Healthcheck endpoints respond healthy for Qdrant, Meilisearch, Keycloak, OpenFGA, OpenMeter, and SigNoz.
- [x] **Database Schema Migrations:**
  - [x] Bytebase migration pipeline executes cleanly on Supabase PostgreSQL and SQLite with mandatory peer review gates and rollback (`platform_infra/release/db/bytebase_adapter.py`).
  - [x] Verify rollback migration scripts are present and verified.
- [x] **Cache & Streaming:**
  - [x] Dragonfly responds on port 6379 with latency < 2ms.
  - [x] AutoMQ / Kafka topics partitioned and accessible to event bus.

---

## 4. Deployment & Rollout Procedures

- [x] **Deploy via Kamal:**
  - [x] Execute `kamal deploy` for zero-downtime blue/green container rollout (`platform_infra/release/ci/kamal_adapter.py`).
- [x] **Post-Deployment Sanity Checks:**
  - [x] Ingress gateway responds on `/health`.
  - [x] Authenticate via Keycloak and issue test chat turn in LibreChat.
  - [x] Confirm turn appears in Working Memory and Fact Store.
  - [x] Check SigNoz dashboard for incoming traces and OTLP spans.
  - [x] Check OpenMeter for token usage events.
- [x] **Rollback Contingency:**
  - [x] If healthcheck fails, run `kamal rollback` within 60 seconds (`platform_infra/release/ci/kamal_adapter.py`).
  - [x] Verify database schema compatibility with previous release tag (`platform_infra/release/db/bytebase_adapter.py`).
