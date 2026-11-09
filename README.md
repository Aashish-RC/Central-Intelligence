# Central Intelligence — Aevum CI Brain (Layers 1-11)

Central Intelligence is the unified cognitive infrastructure and AI runtime for the Aevum CI ecosystem. It consolidates all perception, memory, knowledge, reasoning, agency, learning, orchestration, safety, and evaluation layers into a single decoupled, high-performance monorepo.

---

## Architecture Overview (Layers 1-11)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Central Intelligence                       │
│                     The Brain (Layers 1-11)                     │
├───────────────────────────────┬─────────────────────────────────┤
│ Cognitive (Layers 1-7)        │ Control (Layers 8-11)           │
├───────────────────────────────┼─────────────────────────────────┤
│ L1 Perception                 │ L8 Orchestration                │
│   • Translation & Audio/Video │   • Workflow Builder & Engines  │
│   • Speech-to-Text (STT)      │   • OmniRoute Multi-Strategy    │
│                               │   • 109 Workflow Nodes          │
│ L2 Memory                     │                                 │
│   • 4-Tier Memory Engine      │ L9 Context Engineering          │
│   • 4 Graph Stitches          │   • Context Synthesizer         │
│   • FastAPI & MCP Server      │   • Compaction & Summarization  │
│                               │                                 │
│ L3 Knowledge                  │ L10 Safety                      │
│   • RAG Pipelines & APIs      │   • Guardrails & PII Filter     │
│   • Local & Web Search        │   • Secret / Injection Defense  │
│   • 3-Source RRF & FalkorDB   │   • Merkle Audit & Approval     │
│                               │                                 │
│ L4 Reasoning                  │ L11 Evaluation                  │
│   • Model Gateway (47 Feat.)  │   • Evaluation Datasets & Bench │
│   • 4-Path Routing & BYOK     │   • Performance & Drift Tracker │
│   • Multi-Provider Adapters   │   • Langfuse OpenTelemetry OTel │
│                               │                                 │
│ L5 Action                     │                                 │
│   • ReAct Agents & Builder    │                                 │
│   • Tool / MCP Connector Hub  │                                 │
│   • Sandboxes & Browser Auto  │                                 │
│                               │                                 │
│ L6 Output                     │                                 │
│   • Media Generation          │                                 │
│   • Text-to-Speech (TTS)      │                                 │
│   • Image & Multimodal Output │                                 │
│                               │                                 │
│ L7 Learning                   │                                 │
│   • Recommender Subsystem     │                                 │
│   • Skills Packaging & Dist   │                                 │
└───────────────────────────────┴─────────────────────────────────┘
```

---

## Directory Layout

```
central-intelligence/
├── README.md                    # System documentation
├── package.json                 # Monorepo root workspace (pnpm, turbo)
├── pnpm-workspace.yaml          # Workspace definitions
├── turbo.json                   # Turbo pipeline orchestration
├── pyproject.toml               # Python project configuration
├── requirements.txt             # Unified Python dependencies
├── docker-compose.yml           # Local infrastructure (Qdrant, Ollama, Meilisearch, Redis, Chroma)
├── docs/
│   └── architecture.md          # Comprehensive architectural reference
├── cognitive/                   # Layers 1-7 (Python + TypeScript)
│   ├── perception/              # L1 Perception (translation, voice_speech STT)
│   ├── memory/                  # L2 Memory (3-tier memory engine + 4 stitches)
│   ├── knowledge/               # L3 Knowledge (RAG, search, web_search, rag_api)
│   ├── reasoning/               # L4 Reasoning (model-gateway, providers, routing)
│   ├── action/                  # L5 Action (agents, tools, sandboxes, connectors)
│   ├── output/                  # L6 Output (media_gen, TTS voice, image_gen)
│   └── learning/                # L7 Learning (recommender, skills packaging)
└── control/                     # Layers 8-11 (Python + TypeScript)
    ├── orchestration/           # L8 Orchestration (engine, workflow, nodes, debugger)
    ├── context/                 # L9 Context Engineering (compaction, summarization)
    ├── safety/                  # L10 Safety (guardrails, rules, audit, auth, approval)
    └── evaluation/              # L11 Evaluation (tracker, langfuse telemetry)
```

---

## Testing & Verification

### Python Test Suites
```bash
# L2 Memory Engine Tests
python -m pytest cognitive/memory/tests/ -q

# L10 Safety & Guardrails Tests
python -m pytest control/safety/guardrails/tests/ -q
```

### TypeScript Test Suites
```bash
# L4 Reasoning Model-Gateway (137 tests / 47 features)
pnpm --filter @central-intelligence/reasoning test

# L8 Orchestration Engine (14 Scenarios)
pnpm --filter @central-intelligence/orchestration test
```

### Infrastructure Startup
```bash
# Spin up Qdrant, Ollama, Meilisearch, Redis, and Chroma
docker compose up -d
```
