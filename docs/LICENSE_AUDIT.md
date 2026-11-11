# Central Intelligence — License & Provenance Audit

**Repository License:** Apache License 2.0 (see [LICENSE](../LICENSE) and [pyproject.toml](../pyproject.toml))  
**Attribution Notices:** See [NOTICE](../NOTICE) and component `NOTICE` files.

---

## 1. Code Provenance Audit

| Path / Component | Origin / Pattern | License | Compatibility & Action Taken |
|---|---|---|---|
| `control/orchestration/nodes/` (`core/`, `plugins/`, `assistants/`, `contract/`, `allNodes.ts`) | Ported from **Ironclad Rivet** (`packages/core/src/model/nodes`, `packages/core/src/plugins`) | **MIT** | Compatible with Apache-2.0. Attribution & MIT license text preserved in [NOTICE](../NOTICE) and [nodes/NOTICE](../control/orchestration/nodes/NOTICE). |
| `cognitive/reasoning/` | Clean-room / adapted gateway patterns from Portkey (MIT), Bifrost (Apache-2.0), Envoy AI Gateway (Apache-2.0), LiteLLM Core (MIT) | **MIT / Apache-2.0** | Compatible with Apache-2.0. Preserved in [cognitive/reasoning/NOTICE](../cognitive/reasoning/NOTICE). |
| `cognitive/action/connectors/` | ActivePieces piece contract pattern | **MIT** | Compatible with Apache-2.0. |
| `control/billing/engine/` (Lago adapter) | REST client boundary to external Lago service | **Own code (Apache-2.0)** -> external **AGPL-3.0** | Strict HTTP/REST process boundary; zero AGPL code vendored in repository. |

---

## 2. Infrastructure (`docker-compose.yml`) License Audit

All container images in `docker-compose.yml` are pinned to explicit release tags. Services with **non-OSI / source-available / copyleft** licenses are flagged below for commercial/hosted deployment review:

| Service | Image (Pinned) | License | OSI-Approved? | Deployment Constraints & OSI Alternatives |
|---|---|---|---|---|
| `ollama` | `ollama/ollama:0.40.16` | MIT | Yes | Unrestricted |
| `meilisearch` | `getmeili/meilisearch:v1.7.3` | MIT | Yes | Unrestricted |
| `chroma` | `chromadb/chroma:0.4.22` | Apache-2.0 | Yes | Unrestricted |
| `qdrant` | `qdrant/qdrant:v1.8.4` | Apache-2.0 | Yes | Unrestricted |
| `temporal` | `temporalio/auto-setup:1.23.1` | MIT | Yes | Unrestricted |
| `keycloak` | `quay.io/keycloak/keycloak:26.8.2` | Apache-2.0 | Yes | Unrestricted |
| `openfga` | `openfga/openfga:v1.22.1` | Apache-2.0 | Yes | Unrestricted |
| `infisical` | `infisical/infisical:v0.167.8` | MIT | Yes | Unrestricted |
| `hyperswitch` | `juspaydotin/hyperswitch-router:v1.129.0-standalone` | Apache-2.0 | Yes | Unrestricted |
| `livekit` | `livekit/livekit-server:v1.13.11` | Apache-2.0 | Yes | Unrestricted |
| `supabase-db` | `supabase/postgres:15.1.1.78` | Apache-2.0 / PostgreSQL | Yes | Unrestricted |
| `huly` | `hardcoreeng/front:v0.7.432` | EPL-2.0 | Yes (weak copyleft) | Separate container boundary; distribute modifications to Huly under EPL-2.0 if modified |
| **`falkordb`** | `falkordb/falkordb:v4.22.3` | **SSPL-v1** | **No** | **HIGH RISK for hosted SaaS**: SSPL-v1 requires open-sourcing management/hosting stack if offered as a service. **OSI Alternative:** PostgreSQL + Apache AGE (`Apache-2.0`). |
| **`nango`** | `nangohq/nango-server:hosted-0.72.4` | **Elastic-2.0** | **No** | **RESTRICTED**: Cannot offer Nango itself as a hosted/managed third-party service. Internal self-hosting allowed. |
| **`phoenix`** | `arizephoenix/phoenix:version-21.0.0` | **Elastic-2.0** | **No** | **RESTRICTED**: Cannot offer Phoenix as a hosted/managed third-party service. Runs as isolated OTLP sidecar. **OSI Alternative:** OpenTelemetry Collector / SigNoz (`MIT` / `Apache-2.0` core). |
| **`dragonfly`** | `docker.dragonflydb.io/dragonflydb/dragonfly:v1.27.1` | **BSL-1.1** | **No** | **RESTRICTED**: Cannot offer as a competing managed cache service; converts to Apache-2.0 after 4 years. **OSI Alternative:** Valkey (`BSD-3-Clause`, wire-compatible). |
| **`memgraph`** | `memgraph/memgraph-platform:2.14.1-memgraph2.14.1-lab2.11.1` | **BSL-1.1** | **No** | **RESTRICTED**: BSL-1.1 for core DB engine. **OSI Alternative:** NetworkX (in-process) or PostgreSQL + Apache AGE (`Apache-2.0`). |

---

## 3. Automated CI Enforcement

`scripts/check_licenses.py` runs in CI on every push and verifies:
1. Root `LICENSE` and `NOTICE` exist and `pyproject.toml` declares `Apache-2.0`.
2. Every image in `docker-compose.yml` is pinned (no `:latest` tags).
3. No committed default secret fallbacks (e.g., `NANGO_SECRET_KEY:-...`) exist in `docker-compose.yml`.
4. Non-OSI services in `docker-compose.yml` match the audited list in this document (failing CI if a new unreviewed non-OSI image is introduced).
5. Installed Python dependencies are checked for strong-copyleft/unreviewed licenses (flagging GPL/AGPL if accidentally added to `requirements.txt` or `pyproject.toml`).

