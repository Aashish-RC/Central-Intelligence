# Central Intelligence — License & Provenance Audit

**Repository License:** Apache License 2.0 (see [LICENSE](../LICENSE) and [pyproject.toml](../pyproject.toml))
**Attribution Notices:** See [NOTICE](../NOTICE) and component `NOTICE` files.
**Reviewed:** 2026-11-17

---

## 1. Code & Python Lockfile Audit

| Path / Component | Origin / Pattern | License | Compatibility & Action Taken |
|---|---|---|---|
| `control/orchestration/nodes/` (`core/`, `plugins/`, `assistants/`, `contract/`, `allNodes.ts`) | Ported from **Ironclad Rivet** (`packages/core/src/model/nodes`, `packages/core/src/plugins`) | **MIT** | Compatible with Apache-2.0. Attribution & MIT license text preserved in [NOTICE](../NOTICE) and [nodes/NOTICE](../control/orchestration/nodes/NOTICE). |
| `cognitive/reasoning/` | Clean-room / adapted gateway patterns from Portkey (MIT), Bifrost (Apache-2.0), Envoy AI Gateway (Apache-2.0), LiteLLM Core (MIT) | **MIT / Apache-2.0** | Compatible with Apache-2.0. Preserved in [cognitive/reasoning/NOTICE](../cognitive/reasoning/NOTICE). |
| `cognitive/action/connectors/` | ActivePieces piece contract pattern | **MIT** | Compatible with Apache-2.0. |
| `control/billing/engine/` (Lago adapter) | REST client boundary to external Lago service | **Own code (Apache-2.0)** -> external **AGPL-3.0** | Strict `httpx` HTTP/REST process boundary; zero AGPL code or `lago*` client packages vendored/imported (CI-enforced). |
| `requirements.lock` | Hash-pinned Python dependency graph | **Verified transitive graph** | Generated with `uv pip compile --universal --generate-hashes` (129 lightweight packages; `gqlalchemy`/`falkordb` moved to `graph-non-osi` extra so `tensorflow`/`keras` are excluded); no `litellm`; CI installs with `pip install --require-hashes -r requirements.lock`. |

---

## 2. Infrastructure (`docker-compose.yml`) License & Swap Status

Every Compose service is assigned to either the `core` or `optional` profile. Start the live-test stack with `docker compose --profile core up -d`; the unselected profile does not start implicitly. Non-OSI services are profile-gated: Dragonfly (BSL-1.1) is optional, while Redis 7.4 (RSALv2 / SSPL-v1) and MongoDB Community Server (SSPL-v1) are in the opt-in core profile. Lago is AGPL-3.0, an OSI-approved license with strong network-copyleft obligations; it remains attached to `agpl_quarantine_net`. Review each applicable license before deploying the core profile in hosted/SaaS environments.

### OSI-Licensed Services in Compose
| Service | Image | License | Swap Decision & Role |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:v1.20.0` | Apache-2.0 | Default vector store |
| `ollama` | `ollama/ollama:0.40.16` | MIT | Local model serving |
| `meilisearch` | `getmeili/meilisearch:v1.7.3` | MIT | Full-text search |
| `valkey` | `valkey/valkey:8.0.2-alpine` | BSD-3-Clause | Optional Redis-compatible alternative; core uses Dragonfly |
| `chroma` | `chromadb/chroma:0.4.22` | Apache-2.0 | Embedded/offline vector store |
| `temporal` | `temporalio/temporal:1.10.0` | MIT | Durable L8 workflow engine |
| `otel-collector` | `otel/opentelemetry-collector:0.120.0` | Apache-2.0 | **Added as OSI default replacement for Phoenix (`Elastic-2.0`)** telemetry ingestion |
| `keycloak` | `quay.io/keycloak/keycloak:26.8.2` | Apache-2.0 | L12 IAM, SSO, Passkeys |
| `openfga` | `central-intelligence-openfga:v1.22.1` (built locally from OpenFGA `v1.22.1`) | Apache-2.0 | L12 Zanzibar ReBAC; Alpine base image |
| `openfga-postgres` | `postgres:14-alpine` | PostgreSQL License | Persistent OpenFGA datastore |
| `openfga-migrate` | `central-intelligence-openfga:v1.22.1` (built locally from OpenFGA `v1.22.1`) | Apache-2.0 | OpenFGA schema migration helper; Alpine base image |
| `infisical` | `infisical/infisical:v0.167.8` | MIT | L12 Secret vault |
| `infisical-postgres` | `postgres:14-alpine` | PostgreSQL License | Persistent Infisical datastore |
| `hyperswitch` | `juspaydotin/hyperswitch-router:v1.129.0-standalone` | Apache-2.0 | L13 Payment router |
| `livekit` | `livekit/livekit-server:v1.13.11` | Apache-2.0 | L1 WebRTC media server |
| `supabase-db` | `supabase/postgres:15.1.1.78` | Apache-2.0 / PostgreSQL | L15 Relational + `pgvector` + RLS store |
| `apache-age` | `apache/age:release_PG16_1.6.0` | Apache-2.0 | **L2/L3 default open OpenCypher graph DB** (replaces FalkorDB/Memgraph for hosted launches) |
| `huly` | `hardcoreeng/front:v0.7.432` | EPL-2.0 | Separate container boundary; distribute modifications under EPL-2.0 if modified |
| `kafka` | `apache/kafka:3.8.0` | Apache-2.0 | L15 Event messaging backbone |
| `svix` | `svix/svix-server:v1.57.0` | MIT | L15 Webhook delivery service |
| `openmeter` | `ghcr.io/openmeterio/openmeter:v1.0.0-beta.236` | Apache-2.0 | L13 Real-time metering & token ingestion |
| `openmeter-postgres` | `postgres:14.20-alpine3.23@sha256:14f02666642586a64d6fae8ef42d479fd76456a77c73ae8a626b8fe323b76d22` | PostgreSQL License | OpenMeter metadata store |
| `openmeter-clickhouse` | `clickhouse/clickhouse-server:25.12.3-alpine@sha256:74da41cd61db84f652c6364fd30d59e19b7276d34f7c82515f5f0e70d6f325da` | Apache-2.0 | OpenMeter event store |
| `openmeter-sink-worker` | `ghcr.io/openmeterio/openmeter:v1.0.0-beta.236` | Apache-2.0 | Kafka event sink worker |
| `openmeter-balance-worker` | `ghcr.io/openmeterio/openmeter:v1.0.0-beta.236` | Apache-2.0 | Balance worker |
| `openmeter-billing-worker` | `ghcr.io/openmeterio/openmeter:v1.0.0-beta.236` | Apache-2.0 | Billing worker |
| `openmeter-jobs` | `ghcr.io/openmeterio/openmeter:v1.0.0-beta.236` | Apache-2.0 | Scheduled jobs helper |
| `lago-postgres` | `postgres:14-alpine` | PostgreSQL License | Isolated Lago datastore |
| `lago-redis` | `redis:6-alpine` | BSD-3-Clause | Lago cache; Redis 6 predates the 7.4 license change |
| `librechat` | `ghcr.io/danny-avila/librechat:v0.7.7` | MIT | L18 Multi-provider web chat interface |
| `signoz` | `signoz/signoz:v0.150.0` | MIT / Apache-2.0 | L14 APM, distributed tracing & metrics (core FOSS) |
| `uptime-kuma` | `louislam/uptime-kuma:1.23.13` | MIT | L14 Self-hosted status & service monitoring |
| `posthog` | `posthog/posthog:v1.50.0` | MIT | L14 Product analytics & event funnels (core FOSS) |
| `bytebase` | `bytebase/bytebase:3.2.0` | Apache-2.0 | L17 Database schema migration & version control |

### Optional Non-OSI Services (`profiles: ["optional"]`)
| Service | Image | License | OSI Alternative & Hosted-SaaS Rule |
|---|---|---|---|
| `falkordb` | `falkordb/falkordb:v4.22.3` | **SSPL-v1** | Hosted deployments should use `supabase-db` (Postgres + Apache AGE). |
| `memgraph` | `memgraph/memgraph-platform:2.14.1-memgraph2.14.1-lab2.11.1` | **BSL-1.1** | Hosted deployments should use `supabase-db` (Postgres + Apache AGE) or in-memory NetworkX. |
| `phoenix` | `arizephoenix/phoenix:version-21.0.0` | **Elastic-2.0** | Hosted deployments should route OTLP to `otel-collector` (or SigNoz MIT/Apache-2.0 core). |
| `nango` | `nangohq/nango-server:hosted-0.72.4` | **Elastic-2.0** | Self-hosting only; replace with native OAuth broker before offering managed OAuth-as-a-service. |
| `dragonfly` | `docker.dragonflydb.io/dragonflydb/dragonfly:v1.26.1` | **BSL-1.1** | Optional profile only; use Valkey for an OSI-licensed Redis-compatible alternative. |

### Non-OSI Services in Core (`profiles: ["core"]`)
| Service | Image | License | Isolation / Hosted-SaaS Note |
|---|---|---|---|
| `infisical-redis` | `redis:7.4.7-alpine` | **RSALv2 / SSPL-v1** | Redis Community Edition 7.4 is non-OSI; only starts with the opt-in `core` profile. |
| `openmeter-redis` | `redis:7.4.7@sha256:c6e4a82ce60b829a72a21cc4ad4c1c274fa6962eb0d6ac698e8157cbc3fe16a4` | **RSALv2 / SSPL-v1** | Redis Community Edition 7.4 is non-OSI; only starts with the opt-in `core` profile. |
| `librechat-mongodb` | `mongo:7.0.16-jammy` | **SSPL-v1** | MongoDB Community Server is non-OSI; only starts with the opt-in `core` profile. |

### Strong-Copyleft OSI Services in Core (`profiles: ["core"]`)
| Service | Image | License | Isolation / Hosted-SaaS Note |
|---|---|---|---|
| `lago` | `getlago/api:v1.16.0` | **AGPL-3.0 (OSI-approved)** | Strong network-copyleft obligations; isolated on `agpl_quarantine_net`, with REST HTTP/JSON only and no Python package imports/vendoring. |
| `lago-migrate` | `getlago/api:v1.16.0` | **AGPL-3.0 (OSI-approved)** | One-shot database migration helper, isolated on `agpl_quarantine_net`. |
| `lago-worker` | `getlago/api:v1.16.0` | **AGPL-3.0 (OSI-approved)** | Billing worker, isolated on `agpl_quarantine_net`. |

### Upstream License Evidence
- PostgreSQL 14 (`postgres:14-alpine` and the OpenMeter 14.20 image): [REL_14_20 `COPYRIGHT`](https://github.com/postgres/postgres/blob/REL_14_20/COPYRIGHT).
- Redis 7.4.7: [release `LICENSE.txt`](https://github.com/redis/redis/blob/7.4.7/LICENSE.txt) and [Redis licensing overview](https://redis.io/legal/licenses/) (7.4.x is RSALv2 / SSPL-v1; neither is OSI-approved).
- Redis 6: [6.2.18 `COPYING`](https://github.com/redis/redis/blob/6.2.18/COPYING) (BSD-3-Clause).
- MongoDB Community Server 7.0.16: [release `LICENSE-Community.txt`](https://github.com/mongodb/mongo/blob/r7.0.16/LICENSE-Community.txt) (SSPL-v1).
- ClickHouse 25.12.3: [release `LICENSE`](https://github.com/ClickHouse/ClickHouse/blob/v25.12.3.21-stable/LICENSE) (Apache-2.0).
- OpenMeter `v1.0.0-beta.236`: [release `LICENSE`](https://github.com/openmeterio/openmeter/blob/v1.0.0-beta.236/LICENSE) (Apache-2.0).
- Lago `v1.16.0`: [release `LICENSE`](https://github.com/getlago/lago/blob/v1.16.0/LICENSE) (AGPL-3.0).
- OpenFGA `v1.22.1`: [release `LICENSE`](https://github.com/openfga/openfga/blob/v1.22.1/LICENSE) (Apache-2.0).
- Infisical `v0.167.8`: [release `LICENSE`](https://github.com/Infisical/infisical/blob/v0.167.8/LICENSE) (MIT for non-`ee/` source).
- LibreChat `v0.7.7`: [release `LICENSE`](https://github.com/danny-avila/LibreChat/blob/v0.7.7/LICENSE) (MIT).

---

## 3. Automated CI Enforcement

[scripts/check_licenses.py](../scripts/check_licenses.py) runs on every push and pull request and verifies:
1. Root `LICENSE`, `NOTICE`, `control/orchestration/nodes/NOTICE`, `.env.example`, and `pyproject.toml` (`Apache-2.0`).
2. `requirements.lock` exists with `--hash=sha256:` entries and excludes `litellm`, `tensorflow`, `keras`, `gqlalchemy`, `falkordb`, and `lago*`.
3. Zero Python files vendor or import `lago` / `lago_python_client` (preserving the strict AGPL-3.0 REST boundary).
4. Every image in `docker-compose.yml` is explicitly version-pinned (no `:latest`).
5. No committed default secret fallbacks exist in `docker-compose.yml`.
6. Every service in `docker-compose.yml` is assigned to `core` or `optional`; plain `docker compose up` starts no profile-gated services. Dragonfly is optional; the opt-in `core` profile includes non-OSI Redis 7.4 and MongoDB, plus Lago under OSI-approved AGPL-3.0.
7. Installed Python packages are checked for unexpected strong-copyleft licenses.
