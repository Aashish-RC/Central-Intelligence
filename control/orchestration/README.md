# L8 — Orchestration Layer

The Orchestration Layer (`control/orchestration`) provides multi-agent routing, durable workflow execution, human-in-the-loop governance, and agent fleet orchestration for Central-Intelligence.

## Capabilities

- **Workflow Builder & DAG Engine:** Visual and declarative execution graph construction with cycle detection, topological sequencing, and conditional branching (`workflow_builder/`).
- **Temporal Durable Execution (`temporal_adapter.py` / `temporalBridge.ts`):** Fault-tolerant workflow engine supporting state checkpointing and automatic resumption across system restarts or worker crashes. Feature 8.31.
- **Model Engine & Governance:** Multi-tenant quota routing, BYOK / BYOI fallback chains, virtual keys, RPM/TPM rate limiting, and real-time budget caps (`engine/`).
- **Agent Fleet Orchestration & Paperclip Governance (`paperclipAdapter.ts`):** Hierarchical organizational structure (org charts, reporting chains), per-agent and per-team budget allocation/caps, approval threshold gates, and multi-agent fleet telemetry. Features 8.18, 8.48.

## Running Tests

### Python Workflow Builder & Temporal Tests
```bash
python -m pytest control/orchestration/workflow_builder/tests/ -q
```

### TypeScript Orchestration Engine & Paperclip Tests
```bash
cd control/orchestration
npx tsx --test tests/engine.test.ts tests/paperclip.test.ts
```
