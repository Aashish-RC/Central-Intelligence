# Pheonix Agent Layer

Enterprise-grade decoupled agent control plane and execution runtime built on permissively licensed open-source standards (MIT / Apache-2.0).

---

## 1. Architectural Highlights

- **Universal Contract (`AgentManifest`)**: Strict decoupling of the visual/declarative **Builder** studio from the autonomous **Executor** runtime via Pydantic v2 and JSONSchema Draft 2020-12.
- **Autonomy Patterns (Agno + Hermes)**: ReAct multi-step reasoning, dynamic tool discovery, and multi-subagent coordination.
- **Fused Shared Memory (Mem0 + Letta)**:
  - **Tier 1 (Working)**: In-memory session scratchpad with Write-Ahead Logging (WAL) and Redis adapter.
  - **Tier 2 (Facts)**: SQLite / PostgreSQL persistent entity, rule, and constraint store.
  - **Tier 3 (Semantic)**: Qdrant / Chroma vector similarity engine with cosine search.
- **Hardware-Isolated Sandboxing (E2B + Local Docker)**: Ephemeral microVMs for code execution with hard timeouts and security blocklists.
- **Behavioral Guardrails (Parlant)**: Real-time prompt sanitization, secret/credential redaction, and compliance governor.
- **Real-Time Voice (LiveKit WebRTC)**: Sub-second speech-to-speech event loop with WebRTC token negotiation.
- **IDE Connectivity (MCP & REST)**: Native Model Context Protocol (MCP) server and FastAPI REST endpoints.

---

## 2. Directory Layout

```
agent/
├── pyproject.toml                 # Package dependencies and pytest configuration
├── docker-compose.yml             # Orchestration for Qdrant, Redis, Postgres, and Agent API
├── Dockerfile                     # Container build file
├── README.md                      # Developer documentation
├── config.py                      # Unified environment and feature toggles
├── core/
│   ├── manifest.py                # Pydantic schema for AgentManifest contract
│   ├── event_bus.py               # Async pub/sub event dispatcher
│   └── exceptions.py              # Domain exception hierarchy
├── builder/                       # SUB-BRANCH 1: BUILDER
│   ├── compiler.py                # Graph DAG compiler (Langflow / React Flow -> Manifest)
│   ├── schema_validator.py        # JSONSchema and semantic validator
│   └── templates/                 # Pre-packaged blueprints (Coder, Researcher, Support)
├── executor/                      # SUB-BRANCH 2: EXECUTOR
│   ├── runner.py                  # Autonomous execution loop with memory hooks
│   ├── subagent_manager.py        # Multi-subagent task coordinator
│   └── tools/                     # Tool discovery, API, sandbox, and builtins
│       └── builtin/               # Web search, calculator, file I/O
├── memory/                        # SUB-BRANCH 3: FUSED MEMORY
│   ├── manager.py                 # Unified Facade: remember() & recall()
│   ├── cognition.py               # Fact extraction (Mem0) & 3-tier paging (Letta)
│   └── tiers/                     # Working cache, SQLite facts, and vector index
├── guardrails/                    # SUB-BRANCH 4: BEHAVIORAL GOVERNOR
│   ├── parlant_adapter.py         # Parlant API / engine integration
│   └── filter.py                  # Prompt/response policy interceptor & secret masker
├── sandbox/                       # SUB-BRANCH 5: CODE SANDBOX
│   ├── e2b_adapter.py             # E2B cloud microVM manager
│   └── local_docker_adapter.py    # Local guarded subprocess sandbox
├── voice/                         # SUB-BRANCH 6: REAL-TIME VOICE
│   ├── livekit_adapter.py         # LiveKit WebRTC token generator
│   └── voice_agent.py             # Speech-to-speech event loop
├── server/
│   ├── api.py                     # FastAPI REST management API
│   └── mcp.py                     # Model Context Protocol (MCP) server
└── tests/
    ├── test_manifest.py           # Manifest validation & schema tests
    ├── test_builder_to_executor.py# Graph compiler & end-to-end executor tests
    ├── test_memory_integration.py # 3-tier memory persistence & recall tests
    └── test_sandbox_exec.py       # Sandbox isolation and security tests
```

---

## 3. Quickstart

### Running the Test Suite
```bash
python -m pytest tests/
```

### Running the API Server
```bash
uvicorn server.api:app --host 0.0.0.0 --port 8002 --reload
```

### Starting Infrastructure with Docker Compose
```bash
docker compose up -d
```
