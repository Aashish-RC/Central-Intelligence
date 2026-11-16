# 01 — Compose Service Validation

**Reviewed:** 2026-11-16
**Branch:** `main`
**Baseline revision:** `c6b2cdb99ee3688187c87e2f0bc429517fee8c44`
**Status:** **PARTIAL — Compose definitions validate; live service acceptance is not established**

## Executive summary

The local branch was at the requested baseline revision before these changes. The prior validation report overstated readiness: it labeled the stack a pass while its own matrix recorded unavailable services and skipped live cases. This report supersedes those claims.

The current Compose model renders successfully, the core profile contains 37 services including the Foundry-generated SigNoz deployment, and focused OpenMeter adapter tests pass. No service container was started or stopped, no image was pulled, and no volume was deleted during this execution. **No mandatory service has been proven healthy from a fresh start, and no live integration case is being counted as passed.**

## Configuration changes

| Service/integration | Pinned configuration | Changes made | Runtime status |
|---|---|---|---|
| OpenFGA | OpenFGA `v1.22.1`; PostgreSQL `14-alpine` | Replaced in-memory datastore with a dedicated persistent PostgreSQL datastore and migration job. Added a derived Alpine image so the health check can make an HTTP readiness request instead of merely executing `openfga version`. | Compose-rendered only; image build, migration, and readiness unverified. |
| Infisical | Infisical `v0.167.8`; PostgreSQL `14-alpine`; Redis `7.4.7-alpine` | Added PostgreSQL and Redis backing stores, required database/encryption/auth settings, startup dependencies, persistent volumes, container port `8080` mapped to host `8083`, and an unauthenticated `/api/status` readiness probe. | Compose-rendered only; database initialization and authenticated secret operations unverified. |
| Lago | API `v1.16.0`; PostgreSQL `14-alpine`; Redis `6-alpine` | Added isolated database/cache on `agpl_quarantine_net`, migration job, API and worker commands, required runtime encryption/RSA secrets, persistent volumes, migration dependency, and the upstream `/health` probe. | Compose-rendered only; migrations and API/worker readiness unverified. Existing data is not migrated from the former shared database configuration. |
| OpenMeter | `v1.0.0-beta.236`; existing Kafka `3.9.0`; ClickHouse `25.12.3`; PostgreSQL `14.20`; Redis `7.4.7` | Replaced the floating `main` image and incomplete environment-only setup with the pinned API, sink/balance/billing workers, jobs process, versioned configuration, Kafka connectivity, schema auto-migration, and persistent ClickHouse/PostgreSQL/Redis volumes. Its token meter matches the adapter's `token_consumption` CloudEvent. | Compose-rendered only; registry availability, Kafka connectivity, migrations, event ingestion, and persistence unverified. |
| SigNoz | SigNoz `v0.150.0`; ClickHouse/keeper `25.12.5`; PostgreSQL `16`; ingester pinned to an AMD64 digest | Included the Foundry-generated deployment with ClickHouse, Keeper, metastore, user scripts, and migration dependencies. Host UI remains on `3301`; the collector can reach the ingester on the included network. | Compose-rendered only; images, migrations, trace ingestion/query, and persistence unverified. |
| OpenTelemetry Collector | Collector `0.120.0`, wrapped in Alpine `3.21.3` | Added OTLP gRPC/HTTP receivers, trace/metric/log pipelines, batch and memory-limiter processors, OTLP export to `signoz-ingester`, health extension, and an executable HTTP readiness check. | YAML parsed; Docker image build and exporter connectivity unverified. |
| LibreChat | LibreChat `v0.7.7`; MongoDB `7.0.16-jammy` | Added authenticated MongoDB with durable database/upload storage, the pinned `/health` probe, mounted `librechat.yaml`, and explicit host-gateway networking for the reasoning gateway. The custom endpoint uses the configured `/v1` URL and API key. | Compose-rendered only; MongoDB initialization, UI startup, and UI-to-gateway chat unverified. |
| Supabase / Apache AGE | Existing pinned images | Replaced ephemeral `tmpfs` database storage with the already-declared named volumes so data can survive container recreation. | Configuration only; restart/persistence tests not run. |

`valkey` is now in the `core` profile and `dragonfly` remains `optional`, consistent with the OSI-default cache boundary. Existing named volumes are retained; this change does not remove volumes or migrate existing data.

## Verification evidence

| Command | Result | Qualification |
|---|---:|---|
| `docker compose --profile core config --quiet` | Pass | Final validation used temporary process-only placeholder values for required secrets; no rendered configuration or secrets were printed. Validates Compose syntax/interpolation, not container images or runtime behavior. |
| `docker compose --profile core config --format json` plus YAML parsing of the rendered OpenMeter config and `compose/otel/collector.yaml` | Pass | Confirmed OpenMeter's PostgreSQL migration mode, Kafka/ClickHouse endpoints, and all three collector pipelines parse. |
| `.\.venv\Scripts\python.exe -m pytest -o addopts= control\billing\metering\tests\test_openmeter.py -q` | **5 passed** | Unit tests, not live service tests. Includes HTTP 204 ingestion acceptance. |
| `.\.venv\Scripts\python.exe -m pytest -o addopts= tests\integration\test_live_adapters.py::test_10_4_openmeter_adapter_live -q` | **1 passed** | HTTP calls are mocked; not a live OpenMeter success. |
| `.\.venv\Scripts\python.exe -m pytest -o addopts= control\billing\metering\tests\test_openmeter_live.py::test_live_query_fails_closed_when_openmeter_down -q` | **1 passed** | Expected fail-closed behavior against the local, unused `127.0.0.1:59998` endpoint; not a service integration pass. |
| `.\.venv\Scripts\python.exe -m pytest -o addopts= tests\integration\test_compose_stack_e2e.py --collect-only -q` | **19 collected** | Confirms current collection; does not execute services. |
| Selected 11-scenario preflight in `test_compose_stack_e2e.py` | **10 failed, 1 passed, 8 deselected, 0 skipped** | Live URL/credential variables were blanked only in the test process. Ten cases failed clearly at prerequisite checks before service requests; the sole pass is the explicitly renamed, mocked Kamal command-sequence test and is not live evidence. |

The earlier checkpoint run of `.\.venv\Scripts\python.exe -m pytest -o addopts='' -m live tests/integration/test_live_adapters.py -q` reported **31 passed in 28.09s**. That suite mocks service calls; its OTLP export also logged connection failures to `localhost:4318`. It is not evidence that any listed service was live. The 11 Compose cases now fail fast on missing prerequisites instead of silently skipping.

## Resource and execution limits

- Host: **7.8 GB RAM total, 0.86 GB free** at final check.
- Docker Engine: **29.9.2**, Docker-reported memory limit **3,997,401,088 bytes** (about 3.72 GiB).
- Existing containers observed: `central-qdrant` and `central-apache-age` healthy; `cool_hamilton` was left untouched.
- No Compose `up`, `down`, image pull/build, migration, restart, or volume deletion was performed. The memory headroom is insufficient to safely start the ClickHouse/SigNoz/OpenMeter stack, and image pulls previously encountered registry rate limits.
- No paid service or deployment was invoked.

## Remaining blockers

1. No fresh-start health/readiness evidence exists for the changed services. Compose rendering does not prove that custom images build, database migrations complete, or the pinned tags are available from the current registry.
2. The Foundry SigNoz ingester digest targets AMD64; the Windows host is x86_64, but ARM deployments need a matching manifest digest. Foundry regeneration was performed with its Windows binary and the backslash target path; cross-platform regeneration was not validated.
3. No authorized Infisical machine-identity credentials, Lago API key, Bytebase API token, or reasoning-gateway key/endpoint were configured for this run. Secret values were not inspected or copied into this report.
4. `POSTGRES_LIVE_URL` exists in the local environment, but its integration test was deliberately not run because it creates database objects and the target's disposable/test status was not established.
5. The sandbox scenario was not run because it may invoke a paid external execution service. The real Kamal deployment was not run because deployment is explicitly prohibited; its existing test is now labeled as simulated.
6. LibreChat's service health and reasoning-gateway adapter are individually probeable, but a real authenticated UI request through LibreChat to the gateway remains unverified.

**Release gate:** Sections 10.2 and 11.2 remain incomplete. Do not treat this report as a pass or as approval to proceed to Batch 2.

## Pinned upstream references

- [Infisical v0.167.8 Compose](https://raw.githubusercontent.com/Infisical/infisical/v0.167.8/docker-compose.prod.yml) and [environment requirements](https://raw.githubusercontent.com/Infisical/infisical/v0.167.8/.env.example); the readiness endpoint is documented as [`GET /api/status`](https://infisical.com/docs/api-reference/endpoints/instance/status).
- [Lago v1.16.0 Compose](https://raw.githubusercontent.com/getlago/lago/v1.16.0/docker-compose.yml).
- [OpenMeter v1.0.0-beta.236 quickstart Compose](https://raw.githubusercontent.com/openmeterio/openmeter/v1.0.0-beta.236/quickstart/docker-compose.yaml), [configuration](https://raw.githubusercontent.com/openmeterio/openmeter/v1.0.0-beta.236/quickstart/config.yaml), and [pinned dependency images](https://raw.githubusercontent.com/openmeterio/openmeter/v1.0.0-beta.236/docker-compose.base.yaml).
- [LibreChat v0.7.7 Compose](https://raw.githubusercontent.com/danny-avila/LibreChat/v0.7.7/docker-compose.yml) and [server health route](https://raw.githubusercontent.com/danny-avila/LibreChat/v0.7.7/api/server/index.js).
- [SigNoz Foundry deployment source](../../compose/signoz/casting.yaml).
