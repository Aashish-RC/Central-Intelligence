# Gateway Spec Audit — Locked 219-Feature Spec vs. `cognitive/reasoning` Implementation

> **Upstream Spec Reference:** `aevum_layers.zip` -> `Layer_04_Reasoning_Planning.md` (*"Model access is the locked 219-feature gateway spec, carried over unchanged and not re-listed here."*), `INDEX.md`, `Appendix_B_Mapping.md`  
> **Repo Baseline:** `d:\central-intelligence\cognitive\reasoning\ROADMAP_PROGRESS.md` and on-disk files in `cognitive/reasoning/`  
> **Related Audit:** [`docs/FEATURE_AUDIT.md`](FEATURE_AUDIT.md) (L1–L8 cognitive & orchestration features `1.01`–`8.50`)

---

## 1. Executive Summary & Spec Availability Finding

| Metric / Dimension | Count / Status | Evidence |
|---|---:|---|
| **Locked gateway spec total (per `INDEX.md` & `Layer_04`)** | **219** | Stated in `INDEX.md` (`688 + 219 = 907`) and `Layer_04_Reasoning_Planning.md` |
| **Enumerated sub-features in `aevum_layers.zip` / repo** | **0 (in zip)** / **47 + 4 core + 10 extra (in `ROADMAP_PROGRESS.md`)** | The 219-feature enumeration itself is **not included** in `aevum_layers.zip` or `d:\central-intelligence` |
| **Numbered gateway features tracked (`#1`–`#47` + Core `H1`–`H4`)** | **51** | `cognitive/reasoning/ROADMAP_PROGRESS.md` |
| **Additional L4/security/adapter modules in `cognitive/reasoning/src/`** | **14+** | `hermes`, `openclaw`, `selfKnowledge`, `collaboration`, `synthesis`, `planning`, `goals`, `debate`, `simulation`, `ssrf`, `embeddings`, `security/{consent,residency,wellbeing}` |
| **Clean-room specs on disk (`cognitive/reasoning/docs/specs/`)** | **8 files** | 7 module specs + `interfaces.md` |
| **Quarantined modules (`cognitive/reasoning/quarantine/`)** | **8 files** | Superseded or boundary-quarantined implementations (`cache`, `credits`, `geoip`, `leases`, `pii`, `ratelimit`, `ssrf`, `vault`) |
| **Unenumerated gateway delta (`219 - 47` numbered)** | **172 features** | ⚠️ **Unverifiable without upstream 219-item gateway list** |

> **Honest Spec Gap Statement:** Neither `aevum_layers.zip` nor `d:\central-intelligence` (nor sibling local gateway docs checked during this audit) contains an itemized 219-feature gateway checklist. Consequently, this audit verifies **all 51 core/numbered gateway features (`H1`–`H4`, `#1`–`#47`)**, **10 named roadmap extensions**, **4 clean-room specs**, and **unlisted on-disk modules** inside `cognitive/reasoning/`, and flags the **remaining 172 features** of the locked 219-feature spec as unenumerated pending upstream spec attachment.

---

## 2. Roadmap vs. On-Disk Implementation Table

### 2A. Core Contracts (`H1`–`H4`) & Numbered Gateway Features (`#1`–`#47`)

| ID | Feature (from `ROADMAP_PROGRESS.md`) | Roadmap Status | Actual On-Disk Status | Implementation File(s) | Test File(s) / Evidence |
|---|---|---|---|---|---|
| H1 | Gateway Engine Contract | `built` | ✅ Built | `cognitive/reasoning/src/core/engine.ts`, `src/types/ra1.ts` | `tests/ra1-hooks.test.ts` |
| H2 | Permission & Identity Hook | `built` | ✅ Built | `cognitive/reasoning/src/core/engine.ts`, `src/types/ra1.ts` | `tests/ra1-hooks.test.ts` |
| H3 | Key Lookup Hook (`onKeyLookup`) | `built` | ✅ Built | `cognitive/reasoning/src/core/engine.ts`, `src/security/secrets.ts` | `tests/ra1-hooks.test.ts` |
| H4 | Audit Hook (`onAuditRecord`) | `built` | ✅ Built | `cognitive/reasoning/src/core/engine.ts`, `src/types/ra1.ts` | `tests/ra1-hooks.test.ts`, `tests/repro.test.ts` |
| #1 | OpenAI Chat Completions Endpoint | `built` | ✅ Built | `cognitive/reasoning/src/core/server.ts`, `src/types/chat.ts` | `tests/chat-conformance.test.ts` |
| #2 | Provider Translation (6 Runtimes) | `built` | ✅ Built | `cognitive/reasoning/src/providers/{openai,anthropic,gemini,ollama,bedrock,local,registry}.ts`, `go-providers/` | `tests/gateway.test.ts`, `go-providers/*/*_test.go` |
| #3 | SSE Streaming Normalization | `built` | ✅ Built | `cognitive/reasoning/src/core/stream.ts` | `tests/stream-failover.test.ts` |
| #4 | Dynamic Fallback Chains & Cooldown Tracking | `built` | ✅ Built | `cognitive/reasoning/src/resilience/cooldown.ts`, `src/routing/router.ts`, `src/core/engine.ts` | `tests/gateway.test.ts`, `tests/repro.test.ts` |
| #5 | Model Aliasing & Virtual Tiers | `built` | ✅ Built | `cognitive/reasoning/src/index.ts`, `src/routing/router.ts` | `tests/gateway.test.ts` |
| #6 | Local Runtimes (Ollama, llama.cpp, LocalAI) | `built` | ✅ Built | `cognitive/reasoning/src/providers/local.ts`, `src/providers/ollama.ts` | `tests/gateway.test.ts` |
| #7 | Token Accounting & Estimation | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/usage.ts` | `tests/chat-conformance.test.ts` |
| #8 | Token Pricing & Cost Calculation | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/pricing.ts`, `src/telemetry/pricing-data.json` | `tests/gateway.test.ts` |
| #9 | Sliding-Window Request Rate Limiter | `built` | ✅ Built (clean-room) | `cognitive/reasoning/src/resilience/ratelimit.ts`, `docs/specs/sliding-window-rate-limiter.md` | `tests/ratelimit.test.ts`, `tests/repro.test.ts` (supersedes `quarantine/ratelimit.ts`) |
| #10 | Normalized Error Classification | `built` | ✅ Built | `cognitive/reasoning/src/resilience/classifier.ts`, `src/types/resilience.ts` | `tests/gateway.test.ts`, `tests/repro.test.ts` |
| #11 | Prompt Cache Affinity | `built` | ✅ Built | `cognitive/reasoning/src/routing/router.ts`, `src/index.ts` | `tests/gateway.test.ts` |
| #12 | OpenTelemetry GenAI Distributed Spans | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/tracing.ts` | `tests/tracing.test.ts` |
| #13 | Prometheus Metrics (`/metrics`) | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/metrics.ts`, `src/core/server.ts` | `tests/extended-apis.test.ts` |
| #14 | Exact Response Cache | `built` | ✅ Built (clean-room) | `cognitive/reasoning/src/caching/cache.ts`, `docs/specs/exact-response-cache.md` | `tests/cache.test.ts` (supersedes `quarantine/cache.ts`) |
| #15 | Sliding-Window TPM Limiter | `built` | ✅ Built | `cognitive/reasoning/src/resilience/tpm.ts` | `tests/tpm.test.ts` |
| #16 | AWS Bedrock SigV4 Adapter | `built` | ✅ Built | `cognitive/reasoning/src/providers/bedrock.ts` | `tests/bedrock.test.ts` |
| #17 | MCP Tool Gateway & Agent Loop | `built` | ✅ Built (flag-gated) | `cognitive/reasoning/src/mcp/gateway.ts` | `tests/mcp.test.ts`, `tests/feature-flags.test.ts` (`FEATURE_MCP`, temporarily hosted for L1/L5) |
| #18 | Embedded Control Console UI (`/console`) | `built` | ✅ Built (flag-gated) | `cognitive/reasoning/src/ui/console.ts` | `tests/ui.test.ts`, `tests/feature-flags.test.ts` (`FEATURE_CONSOLE_UI`, temporarily hosted for app surface) |
| #19 | Reversible PII Masking & Vault | `built` | ✅ Built (clean-room) | `cognitive/reasoning/src/security/pii.ts`, `src/security/vault.ts`, `docs/specs/reversible-pii-masking.md` | `tests/pii.test.ts`, `tests/vault.test.ts` (supersedes `quarantine/{pii,vault}.ts`) |
| #20 | Realtime Audio/WebSocket API | `built` | ✅ Built | `cognitive/reasoning/src/realtime/gateway.ts` | `tests/realtime.test.ts` |
| #21 | Semantic Vector Caching | `built` | ✅ Built | `cognitive/reasoning/src/caching/semantic.ts` | `tests/semantic-cache.test.ts` |
| #22 | Audio Speech (TTS) & Transcription (STT) | `built` | ✅ Built | `cognitive/reasoning/src/audio/speech.ts` | `tests/audio.test.ts` |
| #23 | Image Generations & Edits API | `built` | ✅ Built | `cognitive/reasoning/src/images/generate.ts` | `tests/images.test.ts` |
| #24 | Batch Processing API | `built` | ✅ Built | `cognitive/reasoning/src/batches/manager.ts` | `tests/batches.test.ts` |
| #25 | Token Counting API | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/tokens.ts` | `tests/tokens.test.ts` |
| #26 | External Secrets Manager & H3 Hook | `built` | ✅ Built (flag-gated) | `cognitive/reasoning/src/security/secrets.ts` | `tests/secrets.test.ts` (`FEATURE_SECRETS_SYNC`, temporarily hosted for L0 vault) |
| #27 | Multi-Tier Hierarchical Budgets | `built` | ✅ Built | `cognitive/reasoning/src/resilience/budgets.ts` | `tests/budgets.test.ts` |
| #28 | Advanced Conditional Routing | `built` | ✅ Built | `cognitive/reasoning/src/routing/conditional.ts` | `tests/conditional-routing.test.ts` |
| #29 | Bring Your Own Key (BYOK) Routing | `built` | ✅ Built | `cognitive/reasoning/src/security/byok.ts`, `cognitive/reasoning/providers/byokAdapter.ts` | `tests/byok.test.ts` |
| #30 | Semantic Reranking API | `built` | ✅ Built | `cognitive/reasoning/src/rerank/router.ts` | `tests/rerank.test.ts` |
| #31 | Large Payload Body Offload | `built` | ✅ Built | `cognitive/reasoning/src/telemetry/body-offload.ts` | `tests/body-offload.test.ts` |
| #32 | Sticky Session Affinity | `built` | ✅ Built | `cognitive/reasoning/src/routing/session-affinity.ts` | `tests/session-affinity.test.ts` |
| #33 | Shadow & Canary Traffic Emulation | `built` | ✅ Built | `cognitive/reasoning/src/routing/shadow.ts` | `tests/shadow.test.ts` |
| #34 | Pre-first-byte Abort & Post-first-byte SSE Error | `built` | ✅ Built | `cognitive/reasoning/src/core/stream-failover.ts` | `tests/stream-failover.test.ts` |
| #35 | Declarative Config Manifest Loader | `built` | ✅ Built | `cognitive/reasoning/src/config/manifest-loader.ts` | `tests/manifest-loader.test.ts` |
| #36 | GCP OAuth2 Token Refresher | `built` | ✅ Built | `cognitive/reasoning/src/providers/gcp-auth.ts` | `tests/gcp-auth.test.ts` |
| #37 | Video Generation API | `built` | ✅ Built | `cognitive/reasoning/src/videos/generator.ts` | `tests/videos.test.ts` |
| #38 | GeoIP Country & Abuse IP Blacklisting | `quarantined, spec only` | ⚠️ **Built (clean-room + quarantine copy)** | `cognitive/reasoning/src/security/geoip.ts` (404L), `docs/specs/geoip-ip-blocking.md`, `quarantine/geoip.ts` | `tests/geoip.test.ts` — roadmap status is stale vs `src/security/geoip.ts` |
| #39 | File Management & Fine-Tuning API | `built` | ✅ Built | `cognitive/reasoning/src/files/manager.ts` | `tests/files.test.ts` |
| #40 | Dynamic Semantic Tool Search | `built` | ✅ Built (flag-gated) | `cognitive/reasoning/src/mcp/tool-search.ts` | `tests/tool-search.test.ts`, `tests/feature-flags.test.ts` (`FEATURE_TOOL_SEARCH`) |
| #41 | Modular Guardrails Pipeline | `built` | ✅ Built | `cognitive/reasoning/src/security/guardrails/pipeline.ts` | `tests/guardrails.test.ts` |
| #42 | Reasoning Content Isolation | `built` | ✅ Built | `cognitive/reasoning/src/security/reasoning.ts` | `tests/reasoning.test.ts` |
| #43 | Common Expression Language (CEL) Engine | `built` | ✅ Built | `cognitive/reasoning/src/routing/cel.ts` | `tests/cel.test.ts` |
| #44 | Dual-Tier Mesh Architecture | `spec only` | ❌ **Missing in repo** | `ROADMAP_PROGRESS.md` cites `docs/deployment-notes.md` (absent in `d:\central-intelligence`; exists only in sibling repo `D:\pheonix-model-gateway\docs\deployment-notes.md`) | None in `cognitive/reasoning/` |
| #45 | Voice Turn Duration Metering & Preflight Leases | `quarantined, spec only` | ⚠️ **Built (clean-room + quarantine copy)** | `cognitive/reasoning/src/realtime/leases.ts` (513L), `docs/specs/voice-duration-metering.md`, `quarantine/leases.ts` | `tests/leases.test.ts` — roadmap status is stale vs `src/realtime/leases.ts` |
| #46 | Prepaid Credit Gating & Automated Webhooks | `quarantined, spec only` | ⚠️ **Built (clean-room + quarantine copy)** | `cognitive/reasoning/src/telemetry/credits.ts` (403L), `docs/specs/prepaid-credit-gating.md`, `quarantine/credits.ts` | `tests/credits.test.ts` — roadmap status is stale vs `src/telemetry/credits.ts` |
| #47 | Agent-to-Agent (A2A) Routing Protocol | `built` | ✅ Built (flag-gated) | `cognitive/reasoning/src/agents/a2a.ts` | `tests/a2a.test.ts`, `tests/feature-flags.test.ts` (`FEATURE_A2A`) |

### 2B. L4 Cognitive Modules & Additional Files in `cognitive/reasoning/`

| Module / Feature | Roadmap Listed? | Actual Status | File(s) | Test File(s) / Spec |
|---|---|---|---|---|
| Hermes Agent Reasoning Loop | Yes | ✅ Built | `cognitive/reasoning/src/agents/hermesAdapter.ts` | `tests/hermes.test.ts` |
| OpenClaw Adapter & Channel Bridge | Yes | ✅ Built | `cognitive/reasoning/src/agents/openclawAdapter.ts` | `tests/openclaw.test.ts` |
| Self-Knowledge Boundary Module (`4.27`) | Yes | ✅ Built | `cognitive/reasoning/src/selfKnowledge/boundaryModule.ts` | `tests/boundaryModule.test.ts` |
| Multi-Agent Collaboration Controls (`4.23`–`4.26`) | Yes | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts` | `tests/collaboration.test.ts` |
| Adaptive Multi-Model Synthesis Engine (PRM + MoA) (`4.08`, `11.14`) | Yes | ✅ Built | `cognitive/reasoning/src/synthesis/{claimDecomposer,moaFusion,prmVerifier,tieredActivation}.ts` | `tests/synthesis/{claim-decompose,moa,prm,tiered}.test.ts` |
| Plan Preview & Cost Estimator (`4.13`, `4.14`) | Yes | ✅ Built | `cognitive/reasoning/src/planning/{costEstimator,planPreview,models}.ts` | `tests/planPreview.test.ts` |
| Goal Persistence & Long-Horizon State (`4.15`) | Yes | ✅ Built | `cognitive/reasoning/src/goals/{goalStore,models}.ts` | `tests/goalPersistence.test.ts` |
| Multi-Agent Debate Orchestrator (`4.05`) | Yes | ✅ Built | `cognitive/reasoning/src/debate/{orchestrator,models}.ts` | `tests/debate.test.ts` |
| Scenario Simulator (`4.06`) | Yes | ✅ Built | `cognitive/reasoning/src/simulation/{scenarioSimulator,models}.ts` | `tests/scenarioSimulator.test.ts` |
| SSRF Guard (Zero-Trust IP & DNS Validation) | Yes | ✅ Built (clean-room) | `cognitive/reasoning/src/security/ssrf.ts` (+ `quarantine/ssrf.ts`) | `tests/ssrf.test.ts`, `docs/specs/ssrf-guard.md` |
| Clean-Room Specs (`docs/specs/`) | Partial (4 of 7 in roadmap) | ✅ Specs on disk | `cognitive/reasoning/docs/specs/{exact-response-cache,geoip-ip-blocking,interfaces,prepaid-credit-gating,reversible-pii-masking,sliding-window-rate-limiter,ssrf-guard,voice-duration-metering}.md` | Verified by clean-room tests |
| Embeddings Generator (`/v1/embeddings`) | ❌ Omitted from roadmap table | ✅ Built | `cognitive/reasoning/src/embeddings/generator.ts` | `tests/extended-apis.test.ts` |
| Security Extensions (`10.29`, `10.32`, `10.35`, `10.55`) | ❌ Omitted from roadmap | ✅ Built | `cognitive/reasoning/src/security/{consent,residency,wellbeing}.ts` | Cross-layer L10 bridges |
| Root Provider Adapters & OmniRoute Helpers | ❌ Omitted from roadmap | ✅ Built | `cognitive/reasoning/providers/{baseAdapter,byoiAdapter,byokAdapter,enterpriseDirect,mockAdapter,openRouterAggregator}.ts`, `routing/{router,selector,taskClassifier}.ts` | Mirrors/supports L8 orchestration adapters |
| Go Provider Adapters | ❌ Omitted from roadmap | ✅ Built | `cognitive/reasoning/go-providers/{provider.go,anthropic/anthropic.go,gemini/gemini.go,generic/generic.go,openai/openai.go}` | `go-providers/*/*_test.go` |

---

## 3. Documentation & Ledger Discrepancies Found

1. **Missing `PROVENANCE_LEDGER.md` in `d:\central-intelligence`:** `cognitive/reasoning/ROADMAP_PROGRESS.md` states *"Status Standard: Derived per-feature from `PROVENANCE_LEDGER.md`"*, yet `PROVENANCE_LEDGER.md` does not exist inside `d:\central-intelligence` (it exists in sibling workspace `D:\pheonix-model-gateway\PROVENANCE_LEDGER.md` and `D:\pheonix\docs\PROVENANCE_LEDGER.md`).
2. **Stale Quarantine Labels for `#38`, `#45`, `#46`:** `ROADMAP_PROGRESS.md` lists GeoIP (`#38`), Voice Turn Duration Metering (`#45`), and Prepaid Credit Gating (`#46`) as `quarantined, spec only`, whereas full clean-room TypeScript modules (`src/security/geoip.ts`, `src/realtime/leases.ts`, `src/telemetry/credits.ts`) and Vitest suites (`tests/{geoip,leases,credits}.test.ts`) exist on disk alongside `quarantine/`.
3. **Missing `#44` Deployment Spec File:** `ROADMAP_PROGRESS.md` points `#44 Dual-Tier Mesh Architecture` to `docs/deployment-notes.md`, which is absent from `d:\central-intelligence/cognitive/reasoning/docs/` (present only in `D:\pheonix-model-gateway\docs\deployment-notes.md`).
4. **Feature Numbering Conflict:** Modular Guardrails Pipeline is numbered `#41` in `cognitive/reasoning/ROADMAP_PROGRESS.md` vs. `#19 Modular Guardrails Pipeline` in the sibling `PROVENANCE_LEDGER.md`.
5. **Unverified Clean-Room Counsel Flag:** Features `#9`, `#14`, `#19` (PII/Vault), and `SSRF Guard` remain marked `Unverified (flagged for counsel)` in `ROADMAP_PROGRESS.md` because session separation relies on process records rather than technical attestation.

---

## 4. Cross-Layer Overlap Analysis (Addressing `Appendix_B_Mapping.md` Open Item)

`aevum_layers/Appendix_B_Mapping.md` flags an open item: *"Compare the locked 219-feature gateway spec with Layers 8 and 10. Caching, routing and guardrail features probably overlap."* Auditing the actual codebase confirms four active overlap zones:

1. **Routing & Model Selection (Gateway vs. L8 `control/orchestration/`):**
   - Gateway (`cognitive/reasoning/src/routing/`, `routing/`) implements low-level fallback chains, prompt-cache affinity, CEL rules (`#43`), sticky sessions (`#32`), conditional rules (`#28`), and shadow/canary emulation (`#33`).
   - L8 (`control/orchestration/engine/routing/`) implements policy-level cost/latency/quality Pareto optimization (`cognitivePolicy.ts`), domain specialists, accuracy-driven second opinion (`8.15`), and duplicated copies of `providers/*.ts` + `routing/{router,selector,taskClassifier}.ts` + `governance/`.
2. **Caching (Gateway `#14`, `#21` vs. L8 `8.44`–`8.47`):**
   - Exact SHA-256 cache (`src/caching/cache.ts`) and Semantic cache (`src/caching/semantic.ts`) live in `cognitive/reasoning/`, while L8 wraps semantic caching via `SemanticCacheBridge` (`control/orchestration/engine/caching/semanticCacheBridge.ts`) and adds Go cache (`control/orchestration/go-cache/cache.go`).
3. **Guardrails, PII, Security & Residency (Gateway `#19`, `#38`, `#41`, `#42`, SSRF vs. L10 `control/safety/`):**
   - Gateway carries inline request/response PII masking/vault (`#19`), prompt-injection/length guardrails (`#41`), GeoIP blocking (`#38`), SSRF DNS/IP validation, plus `security/{consent,residency,wellbeing}.ts` bridging L10 (`control/safety/`).
   - L10 owns authoritative policies, NeMo Guardrails (`control/safety/guardrails/nemo/nemo_adapter.py`), 4-tier PII scrubbers (`control/safety/pii/`), consent (`c15t_adapter.py`), and privacy/residency enforcement (`control/safety/privacy/residency_enforcer.py`).
4. **Temporarily Hosted Non-Gateway Modules (Flag-Gated Off by Default):**
   - `src/mcp/gateway.ts` (`#17`, `FEATURE_MCP`) -> target home Layer 1/5 tool registry
   - `src/mcp/tool-search.ts` (`#40`, `FEATURE_TOOL_SEARCH`) -> target home Layer 1/5 tool registry
   - `src/agents/a2a.ts` (`#47`, `FEATURE_A2A`) -> target home Layer 8 / L2 orchestration
   - `src/security/secrets.ts` (`#26`, `FEATURE_SECRETS_SYNC`) -> target home Layer 0/12 vault
   - `src/ui/console.ts` (`#18`, `FEATURE_CONSOLE_UI`) -> target home app surface

---

## 5. Recommended Actions

1. **Locate & Import the Locked 219-Feature Spec:** Attach the full 219-item gateway feature catalog into `docs/` so the remaining 172 gateway mechanics can be mapped 1:1.
2. **Synchronize `cognitive/reasoning/ROADMAP_PROGRESS.md`:** Reconcile stale `quarantined, spec only` entries (`#38`, `#45`, `#46`), port or remove reference to missing `docs/deployment-notes.md` (`#44`), and copy `PROVENANCE_LEDGER.md` into `cognitive/reasoning/` if intended to remain canonical in-repo.
3. **Deduplicate Gateway vs. L8 Files:** Consolidate duplicate `providers/` and `routing/{router,selector,taskClassifier}.ts` copies between `cognitive/reasoning/` and `control/orchestration/engine/`.

