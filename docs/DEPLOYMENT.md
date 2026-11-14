# Central Intelligence Deployment & Operations Guide

**Document Version:** 1.0.0  
**Target:** Local Docker Compose & Production Cluster Deployment  
**Estimated Setup Time:** < 45 minutes

---

## 1. Prerequisites

Before deploying Central Intelligence, ensure your host environment meets the following specifications:
- **Operating System:** Linux (Ubuntu 22.04+ LTS recommended), macOS, or Windows 11 with WSL2.
- **Docker Engine:** Version 26.0+ with Docker Compose v2.24+.
- **Hardware Minimum:** 8 CPU Cores, 16 GB RAM, 50 GB NVMe SSD.
- **Hardware Recommended:** 16+ CPU Cores, 32+ GB RAM, GPU support (NVIDIA CUDA 12.0+) for local embeddings/inference.

---

## 2. Docker Compose Stack Deployment

Central Intelligence runs ~30 open-source services orchestrated via `docker-compose.yml`.

### 2.1 Step 1: Clone and Configure Environment Variables
```bash
git clone https://github.com/aevum/central-intelligence.git
cd central-intelligence
cp .env.example .env
```

Replace the `replace-with-...` placeholders in `.env` with suitable local secrets
before starting Compose. The required variables are:
```env
# Runtime Environment
ENV=production
CI_TEST_MODE=0
ADAPTER_MODE=live

# Keycloak Identity & Admin
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=change_this_in_production
KEYCLOAK_BASE_URL=http://keycloak:8080

# Required Compose secrets
INFISICAL_ENCRYPTION_KEY=replace_with_32_byte_key
LIVEKIT_KEYS=replace_with_livekit_key: replace_with_livekit_secret
NANGO_SECRET_KEY=replace_with_strong_random_secret
SVIX_JWT_SECRET=replace_with_signing_secret
POSTHOG_SECRET=replace_with_posthog_secret

# OpenFGA Authorization
OPENFGA_HTTP_ADDR=openfga:8081
OPENFGA_STORE_ID=01HQ28Z...

# Storage & Cache
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_postgres_pass
SUPABASE_URL=http://supabase-db:5432
DRAGONFLY_URL=redis://valkey:6379

# Vector Databases
QDRANT_HOST=qdrant
QDRANT_PORT=6333
MEILISEARCH_URL=http://meilisearch:7700
MEILISEARCH_MASTER_KEY=secure_meilisearch_key

# Billing (AGPL Quarantined)
OPENMETER_URL=http://openmeter:8888
LAGO_URL=http://lago:3000
HYPERSWITCH_URL=http://hyperswitch:8080

# Observability
SIGNOZ_OTLP_ENDPOINT=http://signoz:4317
POSTHOG_URL=http://posthog:8090
UPTIME_KUMA_URL=http://uptime-kuma:3001
```

Do not commit `.env` or use these local credentials in production.

### 2.2 Step 2: Launch Stack
Start the core OSS services in detached mode:
```bash
docker compose up -d
```

### 2.3 Step 3: Verify Service Health
Run the automated verification script or inspect container status:
```bash
docker compose ps
```
Key container health checks:
- `central-keycloak`: `http://localhost:8080/health`
- `central-qdrant`: `http://localhost:6333/healthz`
- `central-meilisearch`: `http://localhost:7700/health`
- `central-openmeter`: `http://localhost:8888/healthz`
- `central-temporal`: port `7233` (gRPC) & `8080` (Web UI)

---

## 3. Database Migrations via Bytebase

Central Intelligence database schemas across Supabase PostgreSQL and SQLite are version-controlled and executed automatically:
1. Automated schema discovery is invoked via `platform_infra/release/db/bytebase_adapter.py`.
2. To run pending migrations manually:
   ```bash
   python -m cognitive.memory.storage.migrations
   ```
3. Rollbacks can be verified by querying the migration table:
   ```sql
   SELECT version, applied_at, status FROM schema_migrations ORDER BY version DESC;
   ```

---

## 4. Production Hardening & Security Guidelines

1. **Licensing Quarantine (AGPL Protection):**
   - Lago (`lago:3000`) is quarantined on a private internal docker network. Central Intelligence interacts strictly across JSON-over-HTTP boundaries to maintain AGPL compliance without infectious copyleft propagation.
2. **Fail-Closed Adapter Mode:**
   - Always confirm `ADAPTER_MODE=live` in production. The `production_guard` module halts startup if an unconfigured mock is detected in a live environment.
3. **TLS/SSL Ingress:**
   - In production, bind ports behind an HTTPS reverse proxy (Traefik, Nginx, or Cloudflare Tunnel) with automated Let's Encrypt certificates.
4. **Log Retention & Scrubber:**
   - SigNoz collector pipelines should be paired with the Central Intelligence PII scrubber to ensure raw user secrets are never persisted in observability indices.

---

## 5. Kamal Zero-Downtime Rolling Deployment

For deploying updates without service interruption:
```bash
# Push container image to registry
kamal build

# Deploy new release with health verification
kamal deploy

# In case of healthcheck failure, instantly roll back
kamal rollback
```
