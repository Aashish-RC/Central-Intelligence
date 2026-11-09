# L8 — Orchestration Layer

The Orchestration Layer (`control/orchestration`) provides multi-agent routing, durable workflow execution, human-in-the-loop governance, and agent fleet orchestration for Central-Intelligence.

## Capabilities

- **Workflow Builder & DAG Engine:** Visual and declarative execution graph construction with cycle detection, topological sequencing, and conditional branching (`workflow_builder/`).
- **Temporal Durable Execution (`temporal_adapter.py` / `temporalBridge.ts`):** Fault-tolerant workflow engine supporting state checkpointing and automatic resumption across system restarts or worker crashes. Feature 8.31.
- **Model Engine & Governance:** Multi-tenant quota routing, BYOK / BYOI fallback chains, virtual keys, RPM/TPM rate limiting, and real-time budget caps (`engine/`).
- **Agent Fleet Orchestration & Paperclip Governance (`paperclipAdapter.ts`):** Hierarchical organizational structure (org charts, reporting chains), per-agent and per-team budget allocation/caps, approval threshold gates, and multi-agent fleet telemetry. Features 8.18, 8.48.
- **Cognitive Routing Policy Engine (`cognitivePolicy.ts`):** Multi-criteria routing integrating dynamic prompt complexity assessment, cost-quality Pareto optimization, latency SLAs, domain specialist selection, canary splitting, and declarative policies. Features 8.09 - 8.15.
- **Human Escalation Protocol (`humanProtocol.ts`):** Human-in-the-loop intervention control plane, state snapshots, operator steering injection, and timeout cascades. Features 8.30, 8.50.
- **Semantic Vector Cache Bridge (`semanticCacheBridge.ts`):** Integrates vector similarity caching directly into the ModelEngine dispatch loop, eliminating redundant model invocations and token costs. Feature 8.44.

## Running Tests

### Python Workflow Builder & Temporal Tests
```bash
python -m pytest control/orchestration/workflow_builder/tests/ -q
```

### TypeScript Orchestration Engine Tests
```bash
cd control/orchestration
npx tsx --test tests/engine.test.ts tests/paperclip.test.ts tests/cognitivePolicy.test.ts tests/humanProtocol.test.ts
```
