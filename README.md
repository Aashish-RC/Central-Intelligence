# Central Intelligence — Aevum CI Brain (Layers 1–19)

Central Intelligence is the unified cognitive infrastructure and AI runtime for the Aevum CI ecosystem. It organizes all 19 architectural layers across four domains (`cognitive/`, `control/`, `platform_infra/`, `surface/`) into a single decoupled monorepo.

---

## Architecture Overview (Layers 1–19)

For the canonical layer specification and balance analysis, see [docs/architecture.md](docs/architecture.md).

```
┌───────────────────────────────────────────────────────────────────────────┐
│                   Central Intelligence — The Brain (L1–L19)               │
├─────────────────────────────────────┬─────────────────────────────────────┤
│ Cognitive (L1–L7)                   │ Control (L8–L14)                    │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ L1  Perception (cognitive/perception)│ L8  Orchestration (control/orchestration) │
│ L2  Memory (cognitive/memory)       │ L9  Context Eng. (control/context)  │
│ L3  Knowledge (cognitive/knowledge) │ L10 Safety & Trust (control/safety) │
│ L4  Reasoning (cognitive/reasoning) │ L11 Evaluation (control/evaluation) │
│ L5  Action (cognitive/action)       │ L12 Identity & IAM (control/identity) │
│ L6  Output (cognitive/output)       │ L13 Billing (control/billing)       │
│ L7  Learning (cognitive/learning)   │ L14 Observability (control/observability) │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ Platform Infra (L15–L17)            │ Surface & Ecosystem (L18–L19)       │
├─────────────────────────────────────┼─────────────────────────────────────┤
│ L15 Data & Messaging (platform_infra/data)   │ L18 Interaction (surface/interaction) │
│ L16 Compute & Serving (platform_infra/compute)│ L19 Federation (surface/federation)  │
│ L17 Release & Lifecycle (platform_infra/release)│                                  │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

---

## Directory Layout

```
central-intelligence/
├── README.md                     # Repository overview (Layers 1–19)
├── LICENSE                       # Apache License 2.0
├── NOTICE                        # Third-party attribution notices
├── .env.example                  # Required environment variables & secrets template
├── .github/workflows/ci.yml      # CI workflow (pytest, TypeScript tests, license check)
├── package.json                  # Monorepo root workspace (pnpm, turbo)
├── pnpm-workspace.yaml           # Workspace definitions
├── turbo.json                    # Turbo pipeline orchestration
├── pyproject.toml                # Python project & pytest configuration
├── requirements.txt              # Direct Python dependency constraints
├── requirements.lock             # Cross-platform SHA256-pinned Python lockfile
├── docker-compose.yml            # Version-pinned OSI-default infrastructure (+ opt-in self-hosted profile)
├── tests/integration/
│   └── test_compose_stack_e2e.py # Live Docker Compose E2E tests (Qdrant, Temporal, Keycloak, Valkey)
├── scripts/
│   └── check_licenses.py         # License, compose tag, and secret hygiene verifier
├── docs/
│   ├── architecture.md           # Single-source 19-layer architecture & balance notes
│   ├── LICENSE_AUDIT.md          # Dependency, node provenance, and compose license audit
│   └── DEFERRED_ITEMS.md         # Hardware-dependent & external integration deferrals
├── cognitive/                    # Layers 1–7 (Python + TypeScript)
│   ├── perception/               # L1  Perception (documents, voice, translation, accessibility)
│   ├── memory/                   # L2  Memory (4-tier engine, graph stitches, portability)
│   ├── knowledge/                # L3  Knowledge (RAG pipelines, local & web search)
│   ├── reasoning/                # L4  Reasoning (Model Gateway, routing, BYOK adapters)
│   ├── action/                   # L5  Action (ReAct agents, builder, sandboxes, connectors)
│   ├── output/                   # L6  Output (media_gen, TTS, image route, widgets)
│   └── learning/                 # L7  Learning (recommender, skills packaging & distillation)
├── control/                      # Layers 8–14 (Python + TypeScript)
│   ├── orchestration/            # L8  Orchestration (DAG runner, Rivet nodes, notifications)
│   ├── context/                  # L9  Context Engineering (synthesizer, compaction, cache)
│   ├── safety/                   # L10 Safety, Trust & Privacy (guardrails, audit, approval)
│   ├── evaluation/               # L11 Evaluation & Quality (benchmarks, A/B, Langfuse OTel)
│   ├── identity/                 # L12 Identity & Access Management (auth, Vault, OpenFGA)
│   ├── billing/                  # L13 Entitlements & Billing (Lago, Hyperswitch, budgets)
│   └── observability/            # L14 Observability (OpenTelemetry, Phoenix, SLOs, replay)
├── platform_infra/               # Layers 15–17 (Python)
│   ├── data/                     # L15 Data & Messaging (AutoMQ, Supabase/RLS, sync, lineage)
│   ├── compute/                  # L16 Compute & Model Serving (vLLM, Ollama, GPU pools)
│   └── release/                  # L17 Release & Lifecycle (CI gates, flags, schema guards)
└── surface/                      # Layers 18–19 (Python + TypeScript)
    ├── interaction/              # L18 Interaction (universal adapters, streaming, desktop/web)
    └── federation/               # L19 Specialization & Federation (brain factory, sync, Huly)
```

---

## Setup

```bash
# 1. Create and configure the required local environment file
cp .env.example .env
# Replace every `replace-with-...` value in .env with a suitable secret.

# 2. Install SHA256-verified Python dependencies
pip install --require-hashes -r requirements.lock

# 3. Install Node/TypeScript workspace dependencies
pnpm install --frozen-lockfile
```

For optional Python extras, install with `pip install -e '.[observability,perception]'`.
The PaddleOCR engine dependencies are only available on Python versions below 3.14;
the perception extra still installs `faster-whisper` on Python 3.14 and newer.

### Default Graph & Infrastructure Stack

- **Default graph backend (L2 Memory & L3 Knowledge):** **PostgreSQL + Apache AGE (`apache-age`, Apache-2.0)** on port `5433` (`MEMORY_GRAPH_BACKEND=postgres_age`, powered by `ApacheAGEAdapter` / `ApacheAGEGraphAdapter`), falling back to in-memory NetworkX when offline or configured with `:memory:`.
- **Opt-in non-OSI self-hosted graph engines:** FalkorDB (`SSPL-v1`) and Memgraph (`BSL-1.1`) are disabled by default behind `profiles: ["self-hosted-non-osi"]` and require installing the optional `.[graph-non-osi]` extra (`docker compose --profile self-hosted-non-osi up -d`). See [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).

---

## Testing & Verification

### Python Test Suite (Layers 1–19)
```bash
# Run the full Python suite (local/offline unit & integration suite)
python -m pytest -q

# Target a single layer suite
python -m pytest cognitive/memory/tests/ -q
python -m pytest control/safety/guardrails/tests/ -q

# Live Adapters Verification Suite (Tasks 10.1 - 10.10)
python -m pytest tests/integration/test_live_adapters.py -v

# Full Stack 14-Step E2E Flow (Tasks 11.1 - 11.6)
python -m pytest tests/integration/test_e2e_full_flow.py -v

# High-Concurrency Load Tests (1000 concurrent reqs, P99 < 5s) (Task 12.1)
python -m pytest tests/load/ -v

# Live Docker Compose E2E tests (starts/uses Qdrant, Apache AGE, Temporal, Keycloak, Valkey)
COMPOSE_E2E_AUTO_START=1 python -m pytest -m live tests/integration/test_compose_stack_e2e.py -v
```

### TypeScript Test Suites
```bash
# Workspace suites (L4 Reasoning, L6 Output, L8 Orchestration scenario smoke)
pnpm test

# L5 Action connectors Vitest suite
pnpm run test:connectors

# L8 Orchestration full scenario runner
pnpm run test:orchestration

# L18 Interaction surface adapter tests
pnpm run test:surface
```

---

## Documentation

- [System Architecture Specification (L1–L19)](docs/ARCHITECTURE.md)
- [Unified REST API Documentation](docs/API.md)
- [Security Review & Hardening Audit](docs/SECURITY_REVIEW.md)
- [Deployment & Operations Guide](docs/DEPLOYMENT.md)
- [Production Release Checklist](docs/RELEASE_CHECKLIST.md)
- [License Audit & Quarantine](docs/LICENSE_AUDIT.md)
- [Feature Audit & Matrix](docs/FEATURE_AUDIT.md)

### License & Infrastructure Checks
```bash
# Verify LICENSE/NOTICE, pinned compose tags, secret requirements, and Python dep licenses
python scripts/check_licenses.py

# Validate docker-compose configuration (with .env populated)
docker compose config -q
```
