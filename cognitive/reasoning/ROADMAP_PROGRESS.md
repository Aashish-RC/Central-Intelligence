# ra1 Model Gateway — Feature Roadmap Progress & Checkpoint Log

> **Engine Core:** TypeScript (strict ESM, Node.js LTS, Hono, Zod, Web Streams, Vitest)  
> **Status Standard:** Derived per-feature from `PROVENANCE_LEDGER.md`. No per-repo percentages.  
> **Test Suite:** 40 test suites, 140 passing tests hermetically executed.

---

## 1. Feature Status Table

| Feature | Status | License Treatment | Reviewed by Human | Verification Evidence |
|:---|:---:|:---|:---:|:---|
| Core H1 Gateway Engine Contract | built | Own implementation | no | `tests/ra1-hooks.test.ts` |
| Core H2 Permission & Identity Hook | built | Own implementation | no | `tests/ra1-hooks.test.ts` |
| Core H3 Key Lookup Hook (`onKeyLookup`) | built | Own implementation | no | `tests/ra1-hooks.test.ts` |
| Core H4 Audit Hook (`onAuditRecord`) | built | Own implementation | no | `tests/ra1-hooks.test.ts`, `tests/repro.test.ts` |
| #1 OpenAI Chat Completions Endpoint | built | Adapted (MIT) | no | `tests/chat-conformance.test.ts` |
| #2 Provider Translation (6 Runtimes) | built | Adapted (MIT / Apache-2.0) | no | `tests/gateway.test.ts` |
| #3 SSE Streaming Normalization | built | Adapted (MIT) | no | `tests/stream-failover.test.ts` |
| #4 Dynamic Fallback Chains & Cooldown Tracking | built | Adapted (Apache-2.0) | no | `tests/gateway.test.ts`, `tests/repro.test.ts` |
| #5 Model Aliasing & Virtual Tiers | built | Adapted (Apache-2.0 / MIT) | no | `tests/gateway.test.ts` |
| #6 Local Runtimes (Ollama, llama.cpp, LocalAI) | built | Own implementation | no | `tests/gateway.test.ts` |
| #7 Token Accounting & Estimation | built | Adapted (MIT) | no | `tests/chat-conformance.test.ts` |
| #8 Token Pricing & Cost Calculation | built | Adapted (Apache-2.0) | no | `tests/gateway.test.ts` |
| #9 Sliding-Window Request Rate Limiter | built | Unverified (flagged for counsel) | no | `tests/repro.test.ts` |
| #10 Normalized Error Classification | built | Adapted (Apache-2.0) | no | `tests/gateway.test.ts`, `tests/repro.test.ts` |
| #11 Prompt Cache Affinity | built | Adapted (Apache-2.0) | no | `tests/gateway.test.ts` |
| #12 OpenTelemetry GenAI Distributed Spans | built | Adapted (MIT) | no | `tests/tracing.test.ts` |
| #13 Prometheus Metrics (`/metrics`) | built | Own implementation | no | `tests/extended-apis.test.ts` |
| #14 Exact Response Cache | built | Unverified (flagged for counsel) | no | `tests/cache.test.ts` |
| #15 Sliding-Window TPM Limiter | built | Adapted (MIT) | no | `tests/tpm.test.ts` |
| #16 AWS Bedrock SigV4 Adapter | built | Adapted (Apache-2.0) | no | `tests/bedrock.test.ts` |
| #17 MCP Tool Gateway & Agent Loop | built | Own implementation from public protocol spec | no | `tests/mcp.test.ts` |
| #18 Embedded Control Console UI (`/console`) | built | Own implementation | no | `tests/ui.test.ts` |
| #19 Reversible PII Masking & Vault | built | Unverified (flagged for counsel) | no | `tests/pii-vault.test.ts` |
| #20 Realtime Audio/WebSocket API | built | Own implementation from public protocol spec | no | `tests/realtime.test.ts` |
| #21 Semantic Vector Caching | built | Adapted (Apache-2.0) | no | `tests/semantic-cache.test.ts` |
| #22 Audio Speech (TTS) & Transcription (STT) | built | Adapted (MIT) | no | `tests/audio.test.ts` |
| #23 Image Generations & Edits API | built | Adapted (MIT) | no | `tests/images.test.ts` |
| #24 Batch Processing API | built | Adapted (MIT) | no | `tests/batches.test.ts` |
| #25 Token Counting API | built | Adapted (Apache-2.0) | no | `tests/tokens.test.ts` |
| #26 External Secrets Manager & H3 Hook | built | Own implementation | no | `tests/secrets.test.ts` |
| #27 Multi-Tier Hierarchical Budgets | built | Adapted (Apache-2.0) | no | `tests/budgets.test.ts` |
| #28 Advanced Conditional Routing | built | Adapted (MIT) | no | `tests/conditional-routing.test.ts` |
| #29 Bring Your Own Key (BYOK) Routing | built | Adapted (MIT) | no | `tests/byok.test.ts` |
| #30 Semantic Reranking API | built | Adapted (MIT) | no | `tests/rerank.test.ts` |
| #31 Large Payload Body Offload | built | Adapted (MIT) | no | `tests/body-offload.test.ts` |
| #32 Sticky Session Affinity | built | Adapted (Apache-2.0) | no | `tests/session-affinity.test.ts` |
| #33 Shadow & Canary Traffic Emulation | built | Adapted (Apache-2.0) | no | `tests/shadow.test.ts` |
| #34 Pre-first-byte Abort & Post-first-byte SSE Error | built | Adapted (Apache-2.0) | no | `tests/stream-failover.test.ts` |
| #35 Declarative Config Manifest Loader | built | Adapted (Apache-2.0) | no | `tests/manifest-loader.test.ts` |
| #36 GCP OAuth2 Token Refresher | built | Adapted (Apache-2.0) | no | `tests/gcp-auth.test.ts` |
| #37 Video Generation API | built | Adapted (MIT) | no | `tests/videos.test.ts` |
| #38 GeoIP Country & Abuse IP Blacklisting | quarantined, spec only | Quarantined | no | Quarantined in `quarantine/geoip.ts` |
| #39 File Management & Fine-Tuning API | built | Adapted (MIT) | no | `tests/files.test.ts` |
| #40 Dynamic Semantic Tool Search | built | Own implementation | no | `tests/tool-search.test.ts` |
| #41 Modular Guardrails Pipeline | built | Adapted (MIT) | no | `tests/guardrails.test.ts` |
| #42 Reasoning Content Isolation | built | Adapted (Apache-2.0) | no | `tests/reasoning.test.ts` |
| #43 Common Expression Language (CEL) Engine | built | Adapted (Apache-2.0) | no | `tests/cel.test.ts` |
| #44 Dual-Tier Mesh Architecture | spec only (`docs/deployment-notes.md`) | Replaced with deployment note | no | `docs/deployment-notes.md` |
| #45 Voice Turn Duration Metering & Preflight Leases | quarantined, spec only | Quarantined | no | Quarantined in `quarantine/leases.ts` |
| #46 Prepaid Credit Gating & Automated Webhooks | quarantined, spec only | Quarantined | no | Quarantined in `quarantine/credits.ts` |
| #47 Agent-to-Agent (A2A) Routing Protocol | built | Own implementation from public protocol spec | no | `tests/a2a.test.ts` |
| SSRF Guard (Zero-Trust IP & DNS Validation) | built | Unverified (flagged for counsel) | no | `tests/ssrf.test.ts` |
| Clean-Room Spec: GeoIP Country & IP Blocking | spec only | Clean-room spec | no | `docs/specs/geoip-ip-blocking.md` |
| Clean-Room Spec: Voice-Duration Metering & Leases | spec only | Clean-room spec | no | `docs/specs/voice-duration-metering.md` |
| Clean-Room Spec: Prepaid Credit Gating & Webhooks | spec only | Clean-room spec | no | `docs/specs/prepaid-credit-gating.md` |
| Clean-Room Spec: Reversible PII Masking | spec only | Clean-room spec | no | `docs/specs/reversible-pii-masking.md` |

---

## 2. Reference Repository Lineage

Permissive sources incorporated under license terms:
- **`portkey-ai-gateway`** (MIT, SHA `669825cbe89ee51569918b8f78a9db486fd69dd4`): Protocol adapters, streaming normalization, handler utilities.
- **`bifrost`** (Apache-2.0, SHA `fa64346b5aabbfa348c0e1e085dc7b3538bc53f3`): Error classification matrix, cooldown tracking, routing strategies.
- **`envoy-ai-gateway`** (Apache-2.0, SHA `12fef6422579f544e84be8167d0979527d3576d4`): Protocol translation patterns, CEL expressions, cost calculation concepts.
- **`litellm`** (MIT, SHA `7e6fb09da3987c8b75062307695f9083da55feed`): Virtual aliasing and endpoint translation patterns.

AGPL repositories (`llmgateway`, `grepture-proxy`) were used as behavior references only. Full license texts are archived in `third_party/licenses/`.
