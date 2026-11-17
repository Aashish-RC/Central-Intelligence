# V1 Deployment Footprints & Profile Architecture

**Author:** Principal Software Architect & Infrastructure Optimization Lead  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Working Revision:** `1269bf30a1f33ab2fad95fc58e6ab4274891c16f`  
**Date:** 2026-11-17  
**Status:** **AUTHORITATIVE FOOTPRINT SPECIFICATION**

---

## 1. Architectural Principles

Central Intelligence v1 defines four distinct deployment footprints. These represent **infrastructure operating profiles**, not commercial pricing tiers:

1. **Lite Profile:** Minimal viable CI capabilities for local development, static analysis, offline unit testing, and edge/desktop developer environments. Strictly engineered to operate within **<= 4.0 GB total system RAM** and <= 2.5 GB Docker memory.
2. **Standard Profile:** Governed Central Intelligence for small-to-medium teams requiring durable workflow state, ReBAC authorization, secrets management, knowledge graph memory, and billing integration. Engineered to run within **<= 8.0 GB total system RAM**.
3. **Enterprise Profile:** Full multi-tenant, horizontally scalable deployment with dedicated analytical datastores (ClickHouse), high-throughput streaming (Kafka), distributed APM observability (SigNoz), and complete container isolation.
4. **Custom Profile:** Capability-driven dynamic profile where services are activated on-demand based on explicit capability declarations.

---

## 2. Profile Comparison & Service Composition Matrix

| Service | Category | Lite Profile | Standard Profile | Enterprise Profile | Custom Profile |
|---|---|:---:|:---:|:---:|:---:|
| `supabase-db` | Relational & Vector | **Active** (Multi-DB) | **Active** (Multi-DB) | **Active** (Dedicated) | Dynamic |
| `valkey` | Cache & Leases | **Active** (Consolidated) | **Active** (Consolidated) | **Active** (Clustered) | Dynamic |
| `qdrant` | Vector ANN Search | Optional (pgvector) | **Active** | **Active** | Dynamic |
| `apache-age` | Knowledge Graph | Optional (In-memory) | **Active** | **Active** | Dynamic |
| `temporal` | Durable Orchestrator | Optional (File store) | **Active** | **Active** | Dynamic |
| `openfga` | ReBAC Authorization | Built-in / In-Memory | **Active** (Shared DB) | **Active** (Dedicated DB) | Dynamic |
| `openfga-postgres` | OpenFGA Datastore | *Merged into supabase* | *Merged into supabase* | **Active** | Dynamic |
| `openfga-migrate` | OpenFGA Migrations | *In-process script* | *In-process script* | **Active** | Dynamic |
| `infisical` | Secrets Management | Built-in AES Keystore | **Active** (Shared DB) | **Active** (Dedicated DB) | Dynamic |
| `infisical-postgres`| Infisical Datastore | *Merged into supabase* | *Merged into supabase* | **Active** | Dynamic |
| `infisical-redis` | Infisical Cache | *Merged into valkey* | *Merged into valkey* | **Active** | Dynamic |
| `bytebase` | Schema Management | Disabled | On-Demand | **Active** | Dynamic |
| `keycloak` | SSO & IAM | Internal JWT | Internal JWT / OIDC | **Active** | Dynamic |
| `otel-collector` | Telemetry Collector | **Active** (File/Console) | **Active** (Batch export) | **Active** (Full pipeline)| Dynamic |
| `lago` | Billing Engine API | Built-in Metering | **Active** (Shared DB) | **Active** (Dedicated DB) | Dynamic |
| `lago-worker` | Billing Worker | Disabled | **Active** | **Active** | Dynamic |
| `lago-postgres` | Lago Datastore | *Merged into supabase* | *Merged into supabase* | **Active** | Dynamic |
| `lago-redis` | Lago Cache | *Merged into valkey* | *Merged into valkey* | **Active** | Dynamic |
| `lago-migrate` | Lago Migrations | Disabled | **Active** (One-shot) | **Active** (One-shot) | Dynamic |
| `openmeter` | Usage Metering API | Built-in SQLite | Built-in / Shared DB | **Active** (ClickHouse/Kafka)| Dynamic |
| `openmeter-workers`| Ingestion & Jobs | Disabled | Disabled | **Active** (4 workers) | Dynamic |
| `openmeter-storage`| ClickHouse/Kafka/DB | Disabled | Disabled | **Active** (3 containers)| Dynamic |
| `signoz-suite` | APM & ClickHouse | Disabled | Disabled | **Active** (7 containers)| Dynamic |
| `librechat-suite` | Web UI & MongoDB | Disabled (Use /console) | Disabled (Use /console) | Optional (`--profile ui`) | Dynamic |

---

## 3. Footprint Resource Budgets & Ceilings

### 3.1 Lite Footprint (Developer & Edge)
- **Target Container Count:** 2 to 4 containers (`valkey`, `supabase-db`, and optionally `qdrant`).
- **Target Idle RAM:** **1.2 – 1.8 GiB**.
- **Target Peak RAM:** **2.2 – 3.2 GiB** (Comfortably inside the 3.72 GiB WSL2 Docker ceiling!).
- **Target CPU Usage:** < 2% idle CPU.
- **Persistent Disk Usage:** ~1.8 GB container images; < 200 MB volume storage.
- **Suitability:** Local development, offline test suites, single-developer laptops, continuous integration (CI) runners, low-cost edge nodes.
- **Launch Command:**
  ```bash
  docker compose --profile lite up -d
  ```

### 3.2 Standard Footprint (Small Team & Governed Production)
- **Target Container Count:** 7 to 9 containers (`valkey`, `supabase-db` [multi-tenant DB], `qdrant`, `apache-age`, `temporal`, `openfga`, `infisical`, `lago`, `otel-collector`).
- **Target Idle RAM:** **3.8 – 5.2 GiB**.
- **Target Peak RAM:** **5.5 – 7.2 GiB**.
- **Target CPU Usage:** 4–8% idle CPU.
- **Persistent Disk Usage:** ~5.5 GB container images; ~1.5 GB volume storage.
- **Suitability:** Small-to-medium enterprise teams (5–50 users), departmental deployments, staging environments, single-node cloud VMs (8–16 GB RAM).
- **Launch Command:**
  ```bash
  docker compose --profile standard up -d
  ```

### 3.3 Enterprise Footprint (Scalable Production)
- **Target Container Count:** 37 to 45 containers (Full distributed stack).
- **Target Idle RAM:** **12.0 – 16.0 GiB**.
- **Target Peak RAM:** **24.0 – 36.0 GiB**.
- **Target CPU Usage:** 15–25% idle CPU.
- **Persistent Disk Usage:** > 12 GB container images; scalable volume storage.
- **Suitability:** Large enterprise deployments (>100 users), high-throughput billing pipelines, mission-critical APM with long-term telemetry retention, multi-node Kubernetes / Swarm clusters.
- **Launch Command:**
  ```bash
  docker compose --profile enterprise up -d
  ```

---

## 4. Resource Quotas & Docker Compose Deploy Ceilings

To eliminate the crash condition (Exit Code 137), all services in `docker-compose.yml` are assigned explicit `deploy.resources.limits` and `deploy.resources.reservations`:

```yaml
services:
  valkey:
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 128M
        reservations:
          cpus: '0.10'
          memory: 32M

  supabase-db:
    deploy:
      resources:
        limits:
          cpus: '1.50'
          memory: 768M
        reservations:
          cpus: '0.25'
          memory: 192M

  qdrant:
    deploy:
      resources:
        limits:
          cpus: '1.00'
          memory: 384M
        reservations:
          cpus: '0.15'
          memory: 64M

  apache-age:
    deploy:
      resources:
        limits:
          cpus: '1.00'
          memory: 512M
        reservations:
          cpus: '0.15'
          memory: 96M

  temporal:
    deploy:
      resources:
        limits:
          cpus: '0.75'
          memory: 256M
        reservations:
          cpus: '0.10'
          memory: 64M
```

These strict limits prevent runaway memory allocation, ensure guaranteed minimum reservations, and prevent kernel OOM killer termination.
