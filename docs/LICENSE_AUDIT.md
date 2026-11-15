# Central Intelligence — License & Provenance Audit

**Repository License:** Apache License 2.0 (see [LICENSE](../LICENSE) and [pyproject.toml](../pyproject.toml))  
**Attribution Notices:** See [NOTICE](../NOTICE) and component `NOTICE` files.

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

Every Compose service is assigned to either the `core` or `optional` profile. Start the live-test stack with `docker compose --profile core up -d`; the unselected profile does not start implicitly. The core stack is not OSI-only: it includes Dragonfly (BSL-1.1) and Lago (AGPL-3.0). Lago remains attached to `agpl_quarantine_net`; review the applicable licenses before deploying the core stack in hosted/SaaS environments.

### OSI-Licensed Services in Compose
| Service | Image (Pinned) | License | Swap Decision & Role |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:v1.20.0` | Apache-2.0 | Default vector store |
| `ollama` | `ollama/ollama:0.40.16` | MIT | Local model serving |
| `meilisearch` | `getmeili/meilisearch:v1.7.3` | MIT | Full-text search |
| `valkey` | `valkey/valkey:8.0.2-alpine` | BSD-3-Clause | Optional Redis-compatible alternative; core uses Dragonfly |
| `chroma` | `chromadb/chroma:0.4.22` | Apache-2.0 | Embedded/offline vector store |
| `temporal` | `temporalio/temporal:1.10.0` | MIT | Durable L8 workflow engine |
| `otel-collector` | `otel/opentelemetry-collector:0.120.0` | Apache-2.0 | **Added as OSI default replacement for Phoenix (`Elastic-2.0`)** telemetry ingestion |
| `keycloak` | `quay.io/keycloak/keycloak:26.8.2` | Apache-2.0 | L12 IAM, SSO, Passkeys |
| `openfga` | `openfga/openfga:v1.22.1` | Apache-2.0 | L12 Zanzibar ReBAC |
| `infisical` | `infisical/infisical:v0.167.8` | MIT | L12 Secret vault |
| `hyperswitch` | `juspaydotin/hyperswitch-router:v1.129.0-standalone` | Apache-2.0 | L13 Payment router |
| `livekit` | `livekit/livekit-server:v1.13.11` | Apache-2.0 | L1 WebRTC media server |
| `supabase-db` | `supabase/postgres:15.1.1.78` | Apache-2.0 / PostgreSQL | L15 Relational + `pgvector` + RLS store |
| `apache-age` | `apache/age:release_PG16_1.6.0` | Apache-2.0 | **L2/L3 default open OpenCypher graph DB** (replaces FalkorDB/Memgraph for hosted launches) |
| `huly` | `hardcoreeng/front:v0.7.432` | EPL-2.0 | Separate container boundary; distribute modifications under EPL-2.0 if modified |
| `kafka` | `apache/kafka:3.8.0` | Apache-2.0 | L15 Event messaging backbone |
| `svix` | `svix/svix-server:v1.57.0` | MIT | L15 Webhook delivery service |
| `openmeter` | `openmeter/openmeter:v1.0.0` | Apache-2.0 | L13 Real-time metering & token ingestion |
| `signoz` | `signoz/signoz:v0.66.0` | MIT / Apache-2.0 | L14 APM, distributed tracing & metrics (core FOSS) |
| `uptime-kuma` | `louislam/uptime-kuma:1.23.13` | MIT | L14 Self-hosted status & service monitoring |
| `posthog` | `posthog/posthog:v1.50.0` | MIT | L14 Product analytics & event funnels (core FOSS) |
| `bytebase` | `bytebase/bytebase:3.2.0` | Apache-2.0 | L17 Database schema migration & version control |
| `librechat` | `ghcr.io/danny-avila/librechat:v0.7.7` | MIT | L18 Multi-provider web chat interface |

### Optional Non-OSI Services (`profiles: ["optional"]`)
| Service | Image (Pinned) | License | OSI Alternative & Hosted-SaaS Rule |
|---|---|---|---|
| `falkordb` | `falkordb/falkordb:v4.22.3` | **SSPL-v1** | Hosted deployments should use `supabase-db` (Postgres + Apache AGE). |
| `memgraph` | `memgraph/memgraph-platform:2.14.1-memgraph2.14.1-lab2.11.1` | **BSL-1.1** | Hosted deployments should use `supabase-db` (Postgres + Apache AGE) or in-memory NetworkX. |
| `phoenix` | `arizephoenix/phoenix:version-21.0.0` | **Elastic-2.0** | Hosted deployments should route OTLP to `otel-collector` (or SigNoz MIT/Apache-2.0 core). |
| `nango` | `nangohq/nango-server:hosted-0.72.4` | **Elastic-2.0** | Self-hosting only; replace with native OAuth broker before offering managed OAuth-as-a-service. |

### Non-OSI/AGPL Services in Core (`profiles: ["core"]`)
| Service | Image (Pinned) | License | Isolation / Hosted-SaaS Note |
|---|---|---|---|
| `dragonfly` | `docker.dragonflydb.io/dragonflydb/dragonfly:v1.26.1` | **BSL-1.1** | Included in the live-test core profile. |
| `lago` | `getlago/api:v1.16.0` | **AGPL-3.0** | Included in core and remains on `agpl_quarantine_net`; zero Python imports/vendoring, REST HTTP/JSON process boundary only. |

---

## 3. Automated CI Enforcement

[scripts/check_licenses.py](../scripts/check_licenses.py) runs on every push and pull request and verifies:
1. Root `LICENSE`, `NOTICE`, `control/orchestration/nodes/NOTICE`, `.env.example`, and `pyproject.toml` (`Apache-2.0`).
2. `requirements.lock` exists with `--hash=sha256:` entries and excludes `litellm`, `tensorflow`, `keras`, `gqlalchemy`, `falkordb`, and `lago*`.
3. Zero Python files vendor or import `lago` / `lago_python_client` (preserving the strict AGPL-3.0 REST boundary).
4. Every image in `docker-compose.yml` is explicitly version-pinned (no `:latest`).
5. No committed default secret fallbacks exist in `docker-compose.yml`.
6. Every service in `docker-compose.yml` is assigned to `core` or `optional`; plain `docker compose up` starts no profile-gated services. The `core` profile includes Dragonfly (BSL-1.1) and Lago (AGPL-3.0).
7. Installed Python packages are checked for unexpected strong-copyleft licenses.
