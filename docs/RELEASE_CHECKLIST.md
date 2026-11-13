# Central Intelligence Production Release Checklist

**Release Target:** Central Intelligence v1.0.0 Production Deployment  
**Coverage:** Layers 1–19, 30+ OSS Container Services, Multi-tier Security & Compliance

---

## 1. Pre-Flight Verification & Automated Tests

- [ ] **Full Regression Test Suite:**
  - [ ] Python backend: `pytest` passes with 0 failures (>1,037 tests).
  - [ ] TypeScript surface: `pnpm test` passes with 0 failures (331 tests).
  - [ ] Total passing tests exceed 1,292 baseline.
- [ ] **Live Adapter Verification Suite:**
  - [ ] `pytest tests/integration/test_live_adapters.py` (31/31 passed).
- [ ] **Full End-to-End 14-Step Flow:**
  - [ ] `pytest tests/integration/test_e2e_full_flow.py` (6/6 passed).
- [ ] **High-Concurrency Load Testing:**
  - [ ] `pytest tests/load/` passes with 1000 concurrent requests, P99 < 5.0s, throughput > 100 ops/sec.

---

## 2. Security & Compliance Review

- [ ] **Fail-Closed Guard:** Verify `control/safety/production_guard.py` enforces fail-closed semantics across all 20+ adapters.
- [ ] **Secret Scanner:** Confirm zero hardcoded production keys (`sk-`, `ghp_`, `AKIA`) exist in repository.
- [ ] **Identity & ReBAC:** Ensure Keycloak JWKS and OpenFGA Zanzibar stores are properly seeded.
- [ ] **Safety & PII:** Verify 4-tier PII scrubber is enabled on all log sinks and memory ingestion pipelines.
- [ ] **Audit Trail:** Verify Merkle audit ledger generates valid SHA-256 root hashes on critical security events.
- [ ] **AGPL Quarantine:** Ensure Lago and AGPL dependencies remain isolated across network boundaries without source linkage.

---

## 3. Infrastructure & Container Validation

- [ ] **Docker Compose:**
  - [ ] All ~30 OSS containers boot without crash loops (`docker compose ps`).
  - [ ] Healthcheck endpoints respond healthy for Qdrant, Meilisearch, Keycloak, OpenFGA, OpenMeter, and SigNoz.
- [ ] **Database Schema Migrations:**
  - [ ] Bytebase migration pipeline executes cleanly on Supabase PostgreSQL and SQLite.
  - [ ] Verify rollback migration scripts are present and verified.
- [ ] **Cache & Streaming:**
  - [ ] Dragonfly responds on port 6379 with latency < 2ms.
  - [ ] AutoMQ / Kafka topics partitioned and accessible to event bus.

---

## 4. Deployment & Rollout Procedures

- [ ] **Deploy via Kamal:**
  - [ ] Execute `kamal deploy` for zero-downtime blue/green container rollout.
- [ ] **Post-Deployment Sanity Checks:**
  - [ ] Ingress gateway responds on `/health`.
  - [ ] Authenticate via Keycloak and issue test chat turn in LibreChat.
  - [ ] Confirm turn appears in Working Memory and Fact Store.
  - [ ] Check SigNoz dashboard for incoming traces and OTLP spans.
  - [ ] Check OpenMeter for token usage events.
- [ ] **Rollback Contingency:**
  - [ ] If healthcheck fails, run `kamal rollback` within 60 seconds.
  - [ ] Verify database schema compatibility with previous release tag.
