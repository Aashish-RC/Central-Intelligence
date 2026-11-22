# Phase A0 — Inventory Freeze & Baseline Measurement Report

**Date:** 2026-11-23  
**Tag:** `ci-v1-baseline`  
**Commit:** `e27eb6596116fa73b859288d60adde0b1c2e2797`  
**Host:** Windows 10/11 x64, Intel Core i5-1035G1 (4C/8T), 8.00 GB RAM (Visible: 8,178,936 KB), WSL2 Docker limit: 3.72 GB  

---

## 1. Executive Summary

Phase A0 marks the formal baseline inventory freeze for the Central Intelligence container consolidation initiative. The current codebase was tagged at `ci-v1-baseline`, all active compose manifests were snapshotted to `compose/snapshots/v1-baseline/`, and the empirical resource readings were cataloged across initial, earlier, and current baselines.

---

## 2. System Requirements Evolution: Initial vs. Earlier vs. Current

| Parameter | Initial Architecture (Legacy Unprofiled) | Earlier Architecture (S4 / Audit Baseline) | Current Baseline (Post-A0 Freeze) | Target Architecture (Post-A15 Consolidated) |
|---|---|---|---|---|
| **Total Declared Services** | 51 services (44 root + 7 SigNoz) | 51 services (with 4 profiles) | 48 services (A1 initial postgres merge started) | 12–16 services max |
| **Always-On Containers (Core Stack)** | 21 containers | 21 containers (unprofiled) / 15 (std) / 3 (lite) | 18 containers (unprofiled) / 12 (std) / 3 (lite) | 6 Always-On (T1) + 3 Warm (T2) |
| **Always-On Memory (Limit Allocation)** | > 24 GB unbounded (OOM 137) | 8,320 MB (Core limit) / 4,480 MB (Std) / 1,280 MB (Lite) | 7,680 MB (Core limit) / 3,840 MB (Std) / 1,280 MB (Lite) | ~2,500 – 3,000 MB Total Limit |
| **Idle Memory (Measured RSS)** | ~6,200 MiB (when running) | ~1,116.3 MiB (Std) / 298.8 MiB (Lite) | ~1,025 MiB (Std) / 298.8 MiB (Lite) | < 750 MiB Measured RSS |
| **Peak Load Memory** | > 24,000 MiB (crashes host) | 4,200 MiB (Std) / 950 MiB (Lite) | 3,800 MiB (Std) / 950 MiB (Lite) | ~1,800 MiB Peak |
| **Host System Requirement (Min)** | 32 GB Dedicated Server | 16 GB Staging / 8 GB (Lite only) | 16 GB Staging / 8 GB (Lite only) | 8 GB Developer PC (Runs Full Stack) |
| **Docker Engine RAM Ceiling** | Unbounded | 3.72 GiB WSL2 ceiling | 3.72 GiB WSL2 ceiling | 3.72 GiB WSL2 ceiling |
| **Pulled Image Disk Footprint** | ~10,650 MB (~10.4 GB) | 10,650 MB (Core) / 2,350 MB (Std) / 510 MB (Lite) | 9,980 MB (Core) / 2,150 MB (Std) / 510 MB (Lite) | ~2,800 MB (-73% reduction) |
| **On-Disk Uncompressed Footprint** | ~26,000 MB (~25.4 GB) | 26,000 MB (Core) / 7,320 MB (Std) / 2,010 MB (Lite) | 24,500 MB (Core) / 6,800 MB (Std) / 2,010 MB (Lite) | ~7,000 MB (-73% reduction) |
| **CPU Utilization (Idle)** | 20% – 35% continuous | 3% – 6% (Std) / < 1.5% (Lite) | 3% – 5% (Std) / < 1.5% (Lite) | < 2.0% Host CPU Idle |

---

## 3. Frozen Baseline Snapshot Artifacts

1. **Git Tag:** `ci-v1-baseline` (pointing to commit `e27eb65`)
2. **Compose Snapshot Directory:** `compose/snapshots/v1-baseline/`
   - `docker-compose.baseline.yml`: Exact copy of root `docker-compose.yml` (40 services)
   - `signoz/compose.yaml`: Exact copy of SigNoz APM stack (7 services)
3. **Reference Benchmarks:** `docs/optimization/V1_RESOURCE_BENCHMARKS.md` and `docs/optimization/ANTIGRAVITY_SYSTEM_REQUIREMENTS_EVALUATION.md`

---

## 4. "Before" Container Resource Table (Baseline for Phase Comparison)

| Container Name | Role | Limit (RAM) | Reservation | Measured RSS (Idle) | Before Status | Consolidation Target |
|---|---|---:|---:|---:|---|---|
| `central-supabase-db` | Primary RDBMS + pgvector | 768M | 192M | 185.1 MiB | Retained (T1) | Absorbs OpenFGA, Infisical, AGE, Temporal, Lago schemas |
| `central-valkey` | Primary In-memory Cache & PubSub | 128M | 32M | 6.5 MiB | Retained (T1) | Absorbs Infisical-redis, Lago-redis |
| `central-qdrant` | Vector Store | 384M | 64M | 53.4 MiB | Active (Core) | Migrates to pgvector in A2; moved to on-demand |
| `central-openfga` | ReBAC Authorization | 128M | 32M | 58.1 MiB | Active (Core) | Schema consolidated into supabase-db |
| `central-infisical` | Secret Management | 512M | 128M | 178.4 MiB | Active (Core) | Cloud-native secrets migration in A8 |
| `central-temporal` | Workflow Engine | 256M | 64M | 168.0 MiB | Active (Core) | DB consolidated into supabase-db; T2 warm pool in A12 |
| `central-lago` | Billing Engine | 384M | 128M | 180.0 MiB | Active (Core) | DB consolidated into supabase-db; handles billing in A6 |
| `central-lago-worker` | Lago Background Worker | 384M | 128M | 160.0 MiB | Active (Core) | T2 warm pool in A12 |
| `central-lago-postgres` | Lago Dedicated DB | 256M | 64M | 48.0 MiB | Active (Core) | Consolidated into supabase-db schema in A1 |
| `central-lago-redis` | Lago Dedicated Redis | 64M | 16M | 14.0 MiB | Active (Core) | Consolidated into valkey DB 2 in A4 |
| `central-keycloak` | IAM Identity Provider | 768M | 256M | 420.0 MiB | Active (Core) | T1 Auth Provider |
| `central-kafka` | Event Bus | 768M | 256M | 380.0 MiB | Active (Core) | Replaced with NATS JetStream in A7 (~500 MB saved) |
| `central-otel-collector` | Telemetry Collector | 192M | 48M | 42.0 MiB | Active (Core) | Retained (Langfuse sink added in A5) |
| `central-bytebase` | DB Schema Management | 256M | 64M | 368.2 MiB | Active (Core) | Moved to dev-time tool in A10 |
| `central-librechat` | UI Chat Interface | 384M | 96M | 160.0 MiB | Active (Core) | Replaced by Hermes surface in A9 |
| `central-librechat-mongodb` | Chat UI Mongo DB | 512M | 128M | 220.0 MiB | Active (Core) | Dropped with LibreChat in A9 |
| `openmeter` (API + 4 workers) | Metering Suite | 1,280M | 320M | 260.0 MiB | Active (Core) | Consolidated into Lago in A6 |
| `openmeter-clickhouse` | Metering OLAP | 768M | 256M | 310.0 MiB | Active (Core) | Dropped in A6 |
| `openmeter-postgres` | Metering DB | 256M | 64M | 48.0 MiB | Active (Core) | Dropped in A6 |
| `openmeter-redis` | Metering Dedupe Redis | 64M | 16M | 15.0 MiB | Active (Core) | Dropped in A6 |
| `signoz` (7 containers) | APM Observability Suite | 2,304M | 700M | 867.0 MiB | Active (Enterprise)| Dropped from runtime in A5 |
| Optional services (12) | Ollama, Meilisearch, etc. | On-Demand | On-Demand | 0 MiB idle | Optional | Dropped or Tier-3 on-demand in A3/A10/A13 |

---

## 5. Phase A0 Outcome & Sign-Off

- **Baseline Status:** FROZEN AND SNAPSHOTTED
- **Git Tag:** `ci-v1-baseline` verified
- **Risks:** None
- **Readiness for Phase A1:** 100% READY
