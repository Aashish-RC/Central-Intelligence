# Central Intelligence — Demo Profile & Legacy Stack Guide (Task A14)

**Profile Name:** `demo`  
**Compose File:** `docker-compose.demo.yml`  
**Purpose:** Preserves 100% backward capability and full visual UIs (LibreChat, MongoDB, Phoenix, SigNoz, Bytebase, PostHog, Uptime Kuma) for client demonstrations, sales meetings, and legacy validation without affecting the lean consolidated production stack.

---

## 1. Quickstart

To spin up the full original demonstration stack on high-memory hardware (16 GB - 32 GB RAM recommended):

```bash
# 1. Provide environment secrets
cp .env.example .env

# 2. Start the complete demo stack
docker compose -f docker-compose.demo.yml --profile demo --profile core up -d

# 3. Stop the demo stack and release all resources
docker compose -f docker-compose.demo.yml --profile demo down
```

---

## 2. Included Demo Services & Endpoints

| Service | UI / Port | Demo Use Case |
|---|---|---|
| **LibreChat** | `http://localhost:3080` | Interactive multi-LLM chat interface with message history |
| **Phoenix** | `http://localhost:6006` | Tracing, LLM evaluations, and hallucination monitoring |
| **SigNoz** | `http://localhost:3301` | Full APM metrics, distributed traces, and log exploration |
| **Bytebase** | `http://localhost:5678` | Visual database schema migrations and approval pipelines |
| **Uptime Kuma** | `http://localhost:3001` | Live status page and HTTP health check dashboards |
| **PostHog** | `http://localhost:8095` | Product funnels and user session analytics |
| **Qdrant Web UI** | `http://localhost:6333/dashboard` | Visual vector collection browser |
| **Keycloak Admin**| `http://localhost:8085/admin` | IAM user directory and OIDC realm management |

---

## 3. Production vs. Demo Architecture Comparison

- **Default Production Stack (`docker-compose.yml`):**
  - Consolidated into Tier 1 (Always-On) + Tier 2 (Warm) + Tier 3 (On-Demand).
  - 6 Always-On containers, < 750 MB RSS idle memory.
  - Runs smoothly on 8 GB RAM developer PCs and edge VMs.

- **Demo Stack (`docker-compose.demo.yml`):**
  - Full 40+ container distributed topology.
  - All standalone datastores and visual web dashboards active.
  - Recommended host: 16–32 GB RAM cloud VM or dedicated demo server.
