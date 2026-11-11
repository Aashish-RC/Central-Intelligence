# Aevum Architecture: Canonical 19-Layer Brain (`L1`–`L19`)

Central Intelligence (`central-intelligence`) is organized into **19 numbered layers** grouped across four domains. This 19-layer numbering is the single canonical architecture across code, documentation, and roadmap tracking (superseding earlier 11-layer and 20-pillar drafts).

## Layer Map (`L1`–`L19`)

### 1. Cognitive Domain (`cognitive/`, Layers 1–7)
| Layer | Name | Directory | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **L1** | Perception | `cognitive/perception/` | Multimodal input parsing (documents/Unstructured, vision, audio/STT, translation, accessibility drivers). |
| **L2** | Memory | `cognitive/memory/` | 4-tier memory engine, graph stitches, retention/privacy controls, and cross-provider portability translators. |
| **L3** | Knowledge | `cognitive/knowledge/` | Hybrid RAG pipelines (3-source RRF), document indexing, vector/graph stores, local and web search. |
| **L4** | Reasoning | `cognitive/reasoning/` | TypeScript Model Gateway, 4-path routing, BYOK key management, streaming inference, and provider adapters. |
| **L5** | Action | `cognitive/action/` | ReAct agents, natural-language agent builder, tool/MCP connectors, sandboxed code execution, browser automation. |
| **L6** | Output | `cognitive/output/` | Multimodal output routing, image/media generation pipelines, TTS synthesis, voice/avatar adapters, and rich widgets. |
| **L7** | Learning | `cognitive/learning/` | Skill extraction/packaging, trajectory distillation, recommender engine, and user-preference adaptation. |

### 2. Control Domain (`control/`, Layers 8–14)
| Layer | Name | Directory | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **L8** | Orchestration | `control/orchestration/` | Visual workflow graph definitions (109 Rivet-origin MIT node specs), Python DAG runner, Temporal integration, and notifications. |
| **L9** | Context Engineering | `control/context/` | Dynamic context assembly, relevance packing, compaction/summarization, and prompt cache management. |
| **L10** | Safety, Trust & Privacy | `control/safety/` | Input/output guardrails, PII redaction, prompt-injection defense, rule evaluation, Merkle audit log, and human approval gates. |
| **L11** | Evaluation & Quality | `control/evaluation/` | Automated regression gates, offline/online LLM judges, A/B statistical testing, drift tracking, and Langfuse instrumentation. |
| **L12** | Identity & Access Management | `control/identity/` | Authentication/MFA/SSO, tenant isolation, OAuth token vault, OpenFGA ReBAC permissions, and Infisical secrets integration. |
| **L13** | Entitlements & Billing | `control/billing/` | Usage metering, Lago billing sync, Hyperswitch payment routing, rate quotas, and hard cost caps. |
| **L14** | Observability | `control/observability/` | OpenTelemetry instrumentation, Arize Phoenix traces, structured logging, health checks, SLO alerts, and execution replay. |

### 3. Platform Infrastructure Domain (`platform_infra/`, Layers 15–17)
| Layer | Name | Directory | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **L15** | Data & Messaging | `platform_infra/data/` | Event streaming (AutoMQ), transactional relational/vector/graph persistence (Supabase/RLS), app isolation, cross-device sync, and lineage. |
| **L16** | Compute & Model Serving | `platform_infra/compute/` | Local/edge inference runtimes (Ollama), high-throughput serving (vLLM), cold/warm GPU pool autoscaling, and spot fallback. |
| **L17** | Release & Lifecycle | `platform_infra/release/` | CI/CD zero-downtime rollout adapters (Kamal/Coolify), feature flags/canaries (GrowthBook), Bytebase schema migration guards, and release quality gates. |

### 4. Surface & Ecosystem Domain (`surface/`, Layers 18–19)
| Layer | Name | Directory | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **L18** | Interaction | `surface/interaction/` | Universal surface rendering adapters (web/LibreChat, desktop/Jan, ambient wake-word, proactive nudges, continuity, depth switcher, settings). |
| **L19** | Specialization & Federation | `surface/federation/` | Domain Brain Factory, privacy-preserving federated learning, tenant pack registry/sandboxing, sharing gates, Huly PM integration, and encrypted inter-brain sync. |

---

## Layer Size & Feature Balance Audit

Measured source inventory across `.py`, `.ts`, `.tsx`, and `.go` files (excluding `node_modules`, `.venv`, and `dist`):

| Layer | Directory | Files | Lines | Notes |
| :--- | :--- | ---: | ---: | :--- |
| L1 | `cognitive/perception` | 59 | 5,110 | Core ingestion/doc/voice active; hardware accessibility drivers deferred ([DEFERRED_ITEMS.md](DEFERRED_ITEMS.md)). |
| L2 | `cognitive/memory` | 63 | 7,530 | Includes 4-tier engine, graph stitches, and portability translators. |
| L3 | `cognitive/knowledge` | 119 | 17,142 | Hybrid search, RAG pipelines, and graph/vector indexing. |
| L4 | `cognitive/reasoning` | 176 | 22,144 | Model Gateway + TypeScript test suites. |
| L5 | `cognitive/action` | 172 | 16,780 | Agents, sandboxes, browser automation, and MCP/connector clients. |
| L6 | `cognitive/output` | 61 | 5,359 | Media generation, TTS, and output routing. |
| L7 | `cognitive/learning` | 57 | 4,752 | Recommender and skill packaging. |
| L8 | `control/orchestration` | 223 | 36,869 | **Skewed by ported node catalog**: ~109 individual Rivet node definitions in `nodes/` (`MIT`) inflate line count relative to core engine code. |
| L9 | `control/context` | 27 | 2,880 | Focused context synthesis, cache, and compaction modules. |
| L10 | `control/safety` | 89 | 11,571 | Guardrails, redteam suite, policy rules, and Merkle audit. |
| L11 | `control/evaluation` | 54 | 8,096 | Benchmarks, A/B experiments, and telemetry. |
| L12 | `control/identity` | 24 | 2,952 | Roadmap tracks 47 features (`12.01`–`12.47`); see `control/identity/ROADMAP_PROGRESS.md`. |
| L13 | `control/billing` | 29 | 3,011 | Roadmap tracks features `13.01`–`13.18` (`13.07` unlisted); see `control/billing/ROADMAP_PROGRESS.md`. |
| L14 | `control/observability` | 32 | 3,163 | Roadmap tracks 24 features (`14.01`–`14.24`); see `control/observability/ROADMAP_PROGRESS.md`. |
| L15 | `platform_infra/data` | 24 | 2,042 | README lists features `15.1`–`15.3`, `15.34`–`15.39` (adapter modules for core data/sync/lineage paths). |
| L16 | `platform_infra/compute` | 25 | 1,525 | README lists features `16.05`, `16.07`, `16.17`, `16.22`–`16.30`. |
| L17 | `platform_infra/release` | 25 | 1,279 | README lists features `17.1`–`17.4`, `17.08`, `17.12`–`17.15`. |
| L18 | `surface/interaction` | 43 | 2,072 | README lists features `18.1`–`18.4`, `18.07`, `18.09`–`18.11`, `18.15`, `18.18`–`18.24`, `18.34`–`18.42`. |
| L19 | `surface/federation` | 31 | 1,688 | README lists features `19.1`, `19.01`–`19.07`, `19.12`–`19.16`, `19.20`, `19.22`–`19.23`, `19.29`–`19.35`. |

### Layer Balance Observations
1. **Why L8 is 36.9k lines**: `control/orchestration/nodes/` contains 109 granular visual-workflow node classes ported from Ironclad Rivet (MIT) alongside their TypeScript schemas and tests. The Python runtime (`control/orchestration/orchestrator/`) is comparable in size to other control layers.
2. **Why L12–L19 are 1.3k–3.2k lines**: L12–L14 consolidate multiple roadmap IDs per adapter module (`ROADMAP_PROGRESS.md` documents full completion across `12.01`–`12.47`, `13.01`–`13.18` minus `13.07`, and `14.01`–`14.24`). L15–L19 implement core vertical-slice adapters whose README tables enumerate specific feature subsets (`15.1–15.39`, `16.05–16.30`, `17.1–17.15`, `18.1–18.42`, `19.1–19.35`) rather than the full specification archive. Features not yet expanded into standalone adapters should be tracked explicitly against the upstream specification archive before declaring L15–L19 feature-complete.

---

## Governance & Licensing References
- Root License: [LICENSE](../LICENSE) (Apache-2.0) and [NOTICE](../NOTICE)
- Third-Party & Compose License Audit: [docs/LICENSE_AUDIT.md](LICENSE_AUDIT.md)
- Deferred Hardware / Infrastructure Items: [docs/DEFERRED_ITEMS.md](DEFERRED_ITEMS.md)
