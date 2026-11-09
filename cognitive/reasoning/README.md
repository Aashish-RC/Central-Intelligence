# ra1 Model Gateway

A high-performance, resilient, multi-provider AI model gateway built in TypeScript (strict ESM, Node.js LTS, Hono, Zod, Web Streams, Vitest) designed as an integrated layer for ra1.

---

## Provenance & Implementation Status

Status is tracked per-feature derived directly from `PROVENANCE_LEDGER.md`. Clean-room behavior specifications are located in `docs/specs/`.

| Feature | Status | License Treatment | Home layer | Hosted in gateway: temporarily, flag off | Reviewed by Human |
|:---|:---:|:---|:---:|:---:|:---:|
| Core H1 `IGatewayEngine` & ra1 Contract | built | Own implementation | Gateway Core | active | no |
| Core H2 Permission Hook (`beforeRequest`) | built | Own implementation | Gateway Core | active | no |
| Core H3 Key Lookup Hook (`onKeyLookup`) | built | Own implementation | Gateway Core | active | no |
| Core H4 Audit Hook (`onAuditRecord`) | built | Own implementation | Gateway Core | active | no |
| #1 OpenAI Chat Endpoint (`/v1/chat/completions`) | built | Adapted (MIT) | Gateway Core | active | no |
| #2 Provider Translation (OpenAI, Anthropic, Gemini, Ollama, Bedrock, Local) | built | Adapted (MIT / Apache-2.0) | Gateway Core | active | no |
| #3 SSE Streaming Normalization | built | Adapted (MIT) | Gateway Core | active | no |
| #4 Fallback Chains & Cooldown Tracking | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #5 Model Aliasing & Virtual Tiers | built | Adapted (Apache-2.0 / MIT) | Gateway Core | active | no |
| #6 Local Runtimes (Ollama, llama.cpp, LocalAI) | built | Own implementation | Gateway Core | active | no |
| #7 Token Accounting & Estimation | built | Adapted (MIT) | Gateway Core | active | no |
| #8 Token Pricing & Cost Engine | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #9 Request Rate Limiter (Sliding Window) | built | Clean-room (implementer saw only the spec) | Gateway Core | active | no |
| #10 Normalized Error Envelope & Mapping | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #11 Prompt Cache Affinity & Routing Strategies | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #12 OpenTelemetry GenAI Distributed Spans | built | Adapted (MIT) | Gateway Core | active | no |
| #13 Prometheus Metrics (`/metrics`) & Health Probes | built | Own implementation | Gateway Core | active | no |
| #14 Exact Response Cache | built | Clean-room (implementer saw only the spec) | Gateway Core | active | no |
| #15 Sliding-Window TPM Limiter | built | Adapted (MIT) | Gateway Core | active | no |
| #16 AWS Bedrock SigV4 Adapter | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #17 MCP Tool Gateway & Agent Loop | built | Own implementation from public protocol spec | Layer 1 tool registry | temporarily, flag off (`FEATURE_MCP`) | no |
| #18 Embedded Control Console UI (`/console`) | built | Own implementation | app surface | temporarily, flag off (`FEATURE_CONSOLE_UI`) | no |
| #19 Reversible PII Masking Engine & Vault | built | Clean-room (implementer saw only the spec) | Gateway Core | active | no |
| #20 Realtime Audio/WebSocket API (`/v1/realtime`) | built | Own implementation from public protocol spec | Gateway Core | active | no |
| #21 Semantic Vector Caching | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #22 Audio Speech (TTS) & Transcription (STT) | built | Adapted (MIT) | Gateway Core | active | no |
| #23 Image Generations & Edits API | built | Adapted (MIT) | Gateway Core | active | no |
| #24 Batch Processing API (`/v1/batches`) | built | Adapted (MIT) | Gateway Core | active | no |
| #25 Token Counting API (`/v1/tokenize`) | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #26 External Secrets Manager & H3 Hook | built | Own implementation | Layer 0 vault | temporarily, flag off (`FEATURE_SECRETS_SYNC`) | no |
| #27 Multi-Tier Hierarchical Budgets | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #28 Advanced Conditional Routing | built | Adapted (MIT) | Gateway Core | active | no |
| #29 Bring Your Own Key (BYOK) Routing | built | Adapted (MIT) | Gateway Core | active | no |
| #30 Semantic Reranking API (`/v1/rerank`) | built | Adapted (MIT) | Gateway Core | active | no |
| #31 Large Payload Body Offload | built | Adapted (MIT) | Gateway Core | active | no |
| #32 Sticky Session Affinity | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #33 Shadow & Canary Traffic Emulation | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #34 Pre-first-byte Abort & Post-first-byte SSE Error | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #35 Declarative Config Manifest Loader | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #36 GCP OAuth2 Token Refresher | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #37 Video Generation API (`/v1/videos`) | built | Adapted (MIT) | Gateway Core | active | no |
| #38 GeoIP Country & Abuse IP Blacklisting | built | Clean-room (implementer saw only the spec) | Layer 0 / Security | temporarily, flag off (`FEATURE_GEOIP`) | no |
| #39 File Management & Fine-Tuning API | built | Adapted (MIT) | Gateway Core | active | no |
| #40 Dynamic Semantic Tool Search | built | Own implementation | Layer 1 tool registry | temporarily, flag off (`FEATURE_TOOL_SEARCH`) | no |
| #41 Modular Guardrails Pipeline | built | Adapted (MIT) | Gateway Core | active | no |
| #42 Reasoning Content Isolation | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #43 Common Expression Language (CEL) Engine | built | Adapted (Apache-2.0) | Gateway Core | active | no |
| #44 Dual-Tier Mesh Architecture | spec only (`docs/deployment-notes.md`) | Replaced with deployment note | Gateway Deployment | spec only | no |
| #45 Voice Turn Duration Metering & Preflight Leases | built | Clean-room (implementer saw only the spec) | Layer 0 Metering | temporarily, flag off (`FEATURE_VOICE_LEASES`) | no |
| #46 Prepaid Credit Gating & Automated Webhooks | built | Clean-room (implementer saw only the spec) | Layer 0 Metering | temporarily, flag off (`FEATURE_PREPAID_CREDITS`) | no |
| #47 Agent-to-Agent (A2A) Routing Protocol | built | Own implementation from public protocol spec | Layer 2 orchestration | temporarily, flag off (`FEATURE_A2A`) | no |
| Hermes Agent Reasoning Loop | built | Adapted (MIT) | Layer 4 reasoning | active | no |
| OpenClaw Adapter & Channel Bridge | built | Adapted (MIT) | Layer 4/5 integration | active | no |
| SSRF Guard (Zero-Trust IP & DNS Validation) | built | Clean-room (implementer saw only the spec) | Gateway Core | active | no |
| Spec: GeoIP Country & IP Blocking | clean-room built | Clean-room spec (`docs/specs/geoip-ip-blocking.md`) | Clean-Room Spec | temporarily, flag off (`FEATURE_GEOIP`) | no |
| Spec: Voice-Duration Metering & Leases | clean-room built | Clean-room spec (`docs/specs/voice-duration-metering.md`) | Clean-Room Spec | temporarily, flag off (`FEATURE_VOICE_LEASES`) | no |
| Spec: Prepaid Credit Gating & Webhooks | clean-room built | Clean-room spec (`docs/specs/prepaid-credit-gating.md`) | Clean-Room Spec | temporarily, flag off (`FEATURE_PREPAID_CREDITS`) | no |
| Spec: Reversible PII Masking | clean-room built | Clean-room spec (`docs/specs/reversible-pii-masking.md`) | Clean-Room Spec | active | no |

---

## Feature Flags (Non-Gateway Modules)

The following non-gateway subsystems belong to outer layers and are temporarily hosted in the gateway repository behind explicit environment feature flags (**OFF by default**):

| Feature Flag | Default | Home Layer | Gated Endpoint(s) | Description |
|:---|:---:|:---|:---|:---|
| `FEATURE_CONSOLE_UI` | `false` | App Surface | `GET /console`, `GET /public` | Web admin control console and interactive playground UI. |
| `FEATURE_MCP` | `false` | Layer 1 tool registry | `GET /v1/mcp/tools`, `POST /v1/mcp/execute` | Model Context Protocol tool registry and tool-call execution loop. |
| `FEATURE_TOOL_SEARCH` | `false` | Layer 1 tool registry | `POST /v1/tools/search` | Dynamic semantic tool search and ranking over tool schemas. |
| `FEATURE_A2A` | `false` | Layer 2 orchestration | `POST /v1/a2a/tasks` | Agent-to-Agent routing protocol task dispatch and capability matching. |
| `FEATURE_SECRETS_SYNC` | `false` | Layer 0 vault | `POST /v1/secrets/sync` | External secrets manager synchronization (Vault/Infisical). The core H3 key-lookup hook remains active regardless. |
| `FEATURE_GEOIP` | `false` | Layer 0 Security | Perimeter Middleware | GeoIP country residency enforcement and abuse IP blacklisting. |
| `FEATURE_VOICE_LEASES` | `false` | Layer 0 Metering | Realtime Audio Hook | Voice turn duration metering and preflight session leases. |
| `FEATURE_PREPAID_CREDITS` | `false` | Layer 0 Metering | Telemetry Audit Hook | Prepaid credit gating preflight checks and automated balance webhooks. |

When any flag is off, the module is not imported at startup and its routes are not registered (returning HTTP 404).

### Hermes Agent Adapter (Multi-Turn Reasoning & Tool Calling)

- **Repo:** [https://github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **License:** MIT
- **Why Chosen:** Enables stateful, multi-turn tool-calling cognitive reasoning loops on top of the model gateway without compromising the gateway's core routing, caching, and governance responsibilities.
- **Usage:**

```typescript
import { HermesAgentAdapter } from '@central-intelligence/reasoning';

const agent = new HermesAgentAdapter({
  name: 'HermesResearchAgent',
  maxTurns: 5,
  tools: [
    {
      name: 'search_database',
      description: 'Search documents by query',
      parameters: { type: 'object', properties: { q: { type: 'string' } }, required: ['q'] },
      handler: async ({ q }) => ({ hits: [`Result for ${q}`] }),
    },
  ],
});

const result = await agent.run('Find documentation about architecture', gatewayDispatcher);
console.log(result.finalResponse);
```

### OpenClaw Adapter (Control Plane & Chat Channels)

- **Repo:** [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
- **License:** MIT
- **Why Chosen:** Coordinates multi-channel messaging dispatch across Discord, Slack, Telegram, WhatsApp, and Microsoft Teams while controlling host OS operations.

---

## Architecture Overview

### ra1 Integration Hooks
- **H1 Contract (`IGatewayEngine`)**: Standardized ra1 interface decoupling high-level orchestration from execution.
- **H2 Permission & Identity Hook (`beforeRequest`, `identityHook`)**: Identity verification (defaults to anonymous for untrusted requests) and access authorization.
- **H3 Key Lookup Hook (`onKeyLookup`)**: Dynamic runtime credential resolution from vault.
- **H4 Audit Hook (`onAuditRecord`)**: Telemetry per request (actor, model, provider, tokens, latency, cost).

### Routing & Resilience
- **Dual Stream Failover**: Pre-first-byte abort & fallback timeout; post-first-byte explicit SSE error guarantees against duplicate tokens.
- **Cooldown Tracking**: Automated cooldown tracking, circuit breaker, and escape routing to local runtimes (Ollama, llama.cpp, LocalAI).
- **Virtual Tiers**: Smart, fast, vision, and embedding routing tiers with load distribution and failover.

### Security & Privacy
- **Reversible PII Masking**: Inbound sensitive entities are substituted with surrogate tokens using the `[TOKEN_<TYPE>_<HEX>]` format before upstream dispatch and restored downstream.

### Adaptive Multi-Model Synthesis Engine (Crown Jewel — Features 4.08, 11.14)
Located in `cognitive/reasoning/src/synthesis/`:
- **Sub-module A: Process Reward Verifier (PRM) (`prmVerifier.ts`):** Step-level scoring (0.0 - 1.0) of intermediate reasoning steps; prunes logically flawed branches before child steps execute.
- **Sub-module B: Claim Decomposition Engine (`claimDecomposer.ts`):** Decomposes reasoning conclusions into atomic claims and cross-verifies factual claims against reference knowledge contexts.
- **Sub-module C: Mixture of Agents (MoA) Fusion Aggregator (`moaFusion.ts`):** Fuses outputs from 3+ parallel candidate models to synthesize complementary insights, resolve disagreements, and compute cross-candidate consensus scores.
- **Sub-module D: Tiered Activation Gate (`tieredActivation.ts`):** Dynamically chooses optimal verification tier:
  - **Tier 0:** Fast-path for simple queries (e.g. arithmetic, greetings) with zero synthesis overhead.
  - **Tier 1:** Single model execution with Claim Decomposition fact-checking.
  - **Tier 2:** Complex queries with PRM step verification and claim validation.
  - **Tier 3:** High-stakes tasks with full MoA fusion (3+ models), PRM verification, and atomic claim corroboration.
  - **Second-Opinion Fallback:** Dynamically escalates to Tier 3 full synthesis if initial accuracy score is below 0.5.

### Plan Preview & Cost Estimator (Features 4.13, 4.14)
Located in `cognitive/reasoning/src/planning/`:
- **Pre-Execution Resource Estimates:** Analyzes scheduled plan steps to forecast prompt/completion token counts, compute costs in USD, and latency duration based on model pricing catalogs.
- **Blast Radius & Risk Evaluation:** Identifies destructive operations (deletions, disk mutations, partition drops) and tags risk severity (`low`, `medium`, `high`, `critical`).
- **Human Approval Gating:** Automatically flags plans that exceed financial budget limits or risk tolerances for human checkpoint review before execution.

### Goal Persistence & Long-Horizon State Store (Feature 4.15)
Located in `cognitive/reasoning/src/goals/`:
- **State Machine & Lifecycle:** Manages long-horizon, multi-session goals with discrete statuses (`pending`, `active`, `paused`, `completed`, `failed`).
- **Hierarchical Subgoals:** Supports sub-goal decomposition, dependency DAGs, output artifact capturing, and dynamic percentage-based completion tracking.
- **Snapshot Checkpoints & Resumption:** Preserves contextual checkpoints mid-execution, enabling reliable rollback or resumption across discontinuous agent execution sessions.

### Multi-Agent Debate Orchestrator (Feature 4.05)
Located in `cognitive/reasoning/src/debate/`:
- **Structured Multi-Turn Dialectic:** Orchestrates formalized debates across agent roles (Proponent, Opponent, Judge) to pressure-test critical conclusions and plans.
- **Convergence & Rebuttal Analysis:** Evaluates confidence divergence, cross-examination rebuttals, and citations across iterative debate rounds.
- **Decisive & Compromise Synthesis:** Emits synthesized verdicts categorizing outcomes into decisive victory, synthesis compromise, or inconclusive flags.

---

## Quick Start

### Installation

```bash
git clone https://github.com/Aashish-RC/pheonix.git
cd services/model-gateway
pnpm install
```

### Running Tests

```bash
pnpm test
```

### Build & Run

```bash
pnpm run build
pnpm run start
```

---

## Documentation Links

- [Feature Roadmap & Checkpoint Log](./ROADMAP_PROGRESS.md)
- [Provenance Ledger](./PROVENANCE_LEDGER.md)
- [Licensing Notice](./NOTICE)
- [Clean-Room Behavior Specifications](./docs/specs/)
- [Deployment Notes (Dual-Tier Mesh)](./docs/deployment-notes.md)
