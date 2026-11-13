# Central Intelligence Platform Audit — 03. Layer-by-Layer Audit

**Baseline:** Commit `138b95b` on branch `main`  
**CI Status:** Passing (GitHub Actions Run `43480953326`)  
**Scope:** Exhaustive audit of all 19 layers across all 4 planes, providing implemented components, missing features, integration status, test coverage, security/operational concerns, dependencies, completion estimates (0–100%), severity-ranked findings, and recommended next actions.

---

## Methodology & Evidence Classification

Each layer is evaluated using the standardized 4-pillar completion model:
1. **Core Domain Logic & Spec (30% weight):** Algorithms, data structures, and state management.
2. **External Integration & Wire Binding (30% weight):** Live protocol/driver connectivity vs in-memory mock.
3. **Security, Multi-Tenancy & Governance (20% weight):** Access control, boundaries, encryption, and auditability.
4. **Verification & Operational Testing (20% weight):** Real integration testing vs mock assertions.

Findings are tagged as:
- `[VERIFIED]`: Directly proven via repository source code, AST, or runtime execution trace.
- `[INFERRED]`: Strongly supported by static code analysis and dependency configurations.
- `[UNVERIFIED]`: Hypothesis requiring live third-party cloud infrastructure to execute.

---

# Plane 1: Cognitive Plane (Layers 1–8)

---

## Layer 1: Perception

- **Location:** `cognitive/perception/` (83 files, 7,172 LOC)
- **Purpose:** Ingests, normalizes, and decodes real-time multimodal sensory streams (audio, speech, vision, OCR, web HTML, documents, screen frames, and hardware accessibility switches).

### 1. Implemented Components
- **LiveKit Audio Adapter:** `cognitive/perception/audio/livekit_adapter.py` (`LiveKitAdapter`, `AudioSession`, `AudioChunk`, lines 34–214). Generates JWT access tokens with `livekit.api.AccessToken`.
- **Handy Speech-to-Text Adapter:** `cognitive/perception/audio/handy_adapter.py` (`HandyAdapter`, `TranscriptionOutput`, lines 53–208).
- **Crawl4AI Web Scraper:** `cognitive/perception/document/crawl4ai_adapter.py` (`Crawl4AIAdapter`, lines 51–230). Converts HTML to clean Markdown with table formatting using BeautifulSoup.
- **PaddleOCR Vision Adapter:** `cognitive/perception/vision/paddleocr_adapter.py` (`PaddleOCRAdapter`, lines 56–182).
- **Screen Awareness:** `cognitive/perception/screen/screenpipe_adapter.py` (`ScreenpipeAdapter`, lines 46–180).
- **Document Parsing:** `cognitive/perception/document/unstructured_adapter.py` (`UnstructuredAdapter`, lines 44–176).
- **Input Normalization & Event Queue:** `cognitive/perception/normalize/event_queue.py` (`UnifiedInputNormalizer`, `EventQueue`, lines 40–165). Synchronizes multimodal events into unified chronological sequence with provenance tagging (`provenance.py`).
- **Code Syntax Parsing:** `cognitive/perception/code/syntax_parser.py` (Python AST and TS/JS/Go import/symbol extraction).

### 2. Missing or Incomplete Components
- **Physical Accessibility Drivers:** `cognitive/perception/accessibility/eye_tracking.py#L48`, `sign_language.py#L46`, and `switch_driver.py#L56` explicitly raise `NotImplementedError("... hardware access not implemented.")`. [VERIFIED]
- **WebRTC Network Socket:** `cognitive/perception/audio/livekit_adapter.py#L182-L188` appends audio chunks to a Python in-memory list `session._stream_buffer` instead of streaming over WebRTC RTP transport. [VERIFIED]
- **Live OCR Fallback:** `cognitive/perception/vision/paddleocr_adapter.py#L153` falls back to hardcoded string `"Central Intelligence System Authorization Badge 2026"` when `paddleocr` engine is unavailable. [VERIFIED]

### 3. Integration Status
- Wires to Layer 9 Context Engineering via normalized event payloads.
- Audio streaming does not establish true WebRTC peer connections with the `livekit:7880` Docker container.

### 4. Test Coverage & Evidence
- 21 test files, 58 test cases.
- `tests/integration/test_live_adapters.py#L76-L120` tests LiveKit and Handy. LiveKit test verifies token length; Handy test injects `MagicMock()` for `_whisper_model`.
- `cognitive/perception/accessibility/tests/test_accessibility.py` asserts that `NotImplementedError` is raised.

### 5. Security & Operational Concerns
- `cognitive/perception/vision/paddleocr_adapter.py#L20` imports `fail_closed_in_production` but **never calls it**. In production, if `PADDLEOCR_ADAPTER_MODE=live` is configured without PaddleOCR installed, it silently returns mock text instead of failing closed. [VERIFIED: F-SEC-02]

### 6. Dependencies & Blockers
- Missing packages in `requirements.lock`: `paddleocr`, `faster-whisper`. Running in live mode triggers `ModuleNotFoundError`.

### 7. Completion Score & Confidence
- **Score: 55%** (Domain: 75%, Integration: 35%, Security: 60%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] Silent Mock Fallback in PaddleOCR:** `paddleocr_adapter.py#L153` returns synthetic text in live production mode without calling `fail_closed_in_production`.
2. **[P1] [VERIFIED] Missing Audio/OCR Runtime Dependencies:** `faster-whisper` and `paddleocr` are omitted from hash-pinned lockfile.
3. **[P2] [VERIFIED] Physical Accessibility Drivers Unimplemented:** Eye tracking, sign language, and switch drivers raise `NotImplementedError`.

### 9. Recommended Next Actions
- Add `faster-whisper` and `paddleocr` to optional extras in `pyproject.toml`.
- Wire `fail_closed_in_production("paddleocr", ...)` before the synthetic string fallback in `paddleocr_adapter.py`.
- Implement real WebRTC data transport in `livekit_adapter.py`.

---

## Layer 2: Memory Hierarchy

- **Location:** `cognitive/memory/` (68 files, 8,554 LOC)
- **Purpose:** 3-tier fused dynamic memory (Working memory with WAL, Relational Facts, Semantic Vector Recall, and Knowledge Graph Relations).

### 1. Implemented Components
- **Unified Engine Facade:** `cognitive/memory/engine.py` (`MemoryEngine`, lines 71–651). Coordinates all tiers and stitches.
- **Tier 1 (Working Memory):** `cognitive/memory/tiers/working/in_memory.py` and `wal.py` with write-ahead log crash recovery; `redis_adapter.py` for Redis/Valkey.
- **Tier 2 (Structured Facts):** `cognitive/memory/tiers/facts/sqlite_adapter.py` (`SQLiteFactStore`) with atomic fact CRUD, schema migrations, and versioning.
- **Tier 3 (Semantic Vectors):** `cognitive/memory/tiers/semantic/qdrant_adapter.py` (`QdrantAdapter`) supporting Qdrant v1.20 `query_points` API; `chroma_adapter.py`.
- **Tier 4 (Graph Memory):** `cognitive/memory/tiers/graph/age_adapter.py` (`ApacheAGEAdapter`) querying PostgreSQL Apache AGE via `pg8000.dbapi`; `_nx_fallback.py` (NetworkX).
- **Stitches & Integrity:** `extractor.py` (Stitch 1), `conflict_resolver.py` (Stitch 3), `synthesizer.py` (Stitch 2), `consolidation.py` (Stitch 4), and `integrity/poisoning_defense.py` (adversarial memory injection filter).
- **Snapshots & Portability:** `snapshots/manager.py` (versioned memory rollback) and `portability/` (export/import).

### 2. Missing or Incomplete Components
- **PostgreSQL Fact Store Driver:** `cognitive/memory/tiers/facts/postgres_adapter.py#L27` attempts `import psycopg2`. `psycopg2` is not installed in the environment (only `pg8000` is in `requirements.lock`). Calling `PostgreSQLFactStore` fails with `AdapterConnectionError`. [VERIFIED: F-DEP-01]
- Dedicated parameterized workflow table is deferred to Layer 8.

### 3. Integration Status
- Wires to Layer 12 IAM via `cognitive/memory/access_control/openfga_bridge.py`.
- Working memory and SQLite facts are fully operational. Qdrant adapter validated against live Qdrant container in CI (`tests/integration/test_compose_stack_e2e.py#L226-L285`).

### 4. Test Coverage & Evidence
- 13 test files, 60 test cases.
- `tests/load/test_load_memory.py` tests 10,000 memory reads/writes against in-memory SQLite and Qdrant.
- `test_access_control.py` validates ReBAC checks.

### 5. Security & Operational Concerns
- Memory access control bridge relies on `OpenFGAAdapter`, which is currently an in-memory simulation. If the process restarts, all ReBAC tuples vanish, allowing potential memory authorization bypass or state inconsistency.

### 6. Dependencies & Blockers
- `psycopg2-binary` missing for PostgreSQL fact store.

### 7. Completion Score & Confidence
- **Score: 80%** (Domain: 90%, Integration: 75%, Security: 80%, Testing: 75%)
- **Confidence: HIGH** (One of the most mature layers).

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] PostgreSQL Fact Store Driver Failure:** `postgres_adapter.py#L27` fails due to uninstalled `psycopg2`.
2. **[P2] [INFERRED] Ephemeral Access Control:** OpenFGA bridge is only as durable as the in-memory tuple set.

### 9. Recommended Next Actions
- Migrate `postgres_adapter.py` from `psycopg2` to `pg8000` or add `psycopg2-binary` to dependencies.
- Wire `openfga_bridge.py` to persistent OpenFGA store.

---

## Layer 3: Knowledge & Retrieval

- **Location:** `cognitive/knowledge/` (84 files, 7,660 LOC)
- **Purpose:** Global Hybrid Search (BM25 lexical + dense vectors), Reciprocal Rank Fusion (RRF), GraphRAG knowledge graph traversal, source provenance, and abstention gating.

### 1. Implemented Components
- **Local Hybrid Search Engine:** `cognitive/knowledge/search/engines/local_hybrid.py` (`LocalHybridSearchEngine`, lines 35–185). Combines SQLite FTS5 / lexical search with dense vector scoring.
- **Reciprocal Rank Fusion:** `cognitive/knowledge/search/engines/rrf.py` (`ReciprocalRankFusion`, $RRF(d) = \sum \frac{1}{60 + r_i(d)}$).
- **Meilisearch Client:** `cognitive/knowledge/search/engines/` (`MeilisearchClient`).
- **GraphRAG:** `cognitive/knowledge/graph/age_adapter.py` (`ApacheAGEGraphAdapter`) executing Cypher queries over Apache AGE.
- **Abstention Engine:** `cognitive/knowledge/abstention/engine.py` (withholds answering when retrieval relevance falls below confidence threshold).
- **Provenance & Quality:** `provenance/tagger.py` (tracks document origin, SHA-256 hash, and copyright) and `quality/scorer.py`.
- **Web Search Engine:** `cognitive/knowledge/web_search/providers/duckduckgo.py` and `verifier/claim_checker.py`.

### 2. Missing or Incomplete Components
- FalkorDB and Memgraph graph adapters are relegated to optional non-OSI profiles.
- Automated document OCR pipeline relies on Layer 1 PaddleOCR (currently stubbed).

### 3. Integration Status
- Wires to Layer 12 IAM via `cognitive/knowledge/access_control/openfga_bridge.py` (DEF-02). Filters retrieval candidates against user permissions before returning search hits.
- Wires to Layer 2 Memory and Layer 9 Context Assembler.

### 4. Test Coverage & Evidence
- 19 test files, 59 test cases.
- `search/tests/test_hybrid_rrf.py`, `test_permission_filter.py`, and `test_meilisearch.py` pass cleanly.
- `tests/integration/test_compose_stack_e2e.py#L326-L340` validates `ApacheAGEGraphAdapter` against live Apache AGE container.

### 5. Security & Operational Concerns
- Permission filtering is evaluated in-memory against `OpenFGAAdapter` tuples; subject to the same persistence limitation as Layer 2.

### 6. Dependencies & Blockers
- None for core OSI operations. Optional `falkordb` and `gqlalchemy` are excluded from lockfile as intended.

### 7. Completion Score & Confidence
- **Score: 75%** (Domain: 80%, Integration: 70%, Security: 75%, Testing: 75%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [INFERRED] Ephemeral Document Permission Enforcement:** Document access filtering depends on in-memory ReBAC tuples.

### 9. Recommended Next Actions
- Verify live Meilisearch HTTP failover when running in production mode.

---

## Layer 4: Reasoning & Planning

- **Location:** `cognitive/reasoning/` (194 files, 23,097 LOC, TypeScript)
- **Purpose:** Multi-provider AI Model Gateway, prompt routing, CEL rules, session affinity, cooldowns, token-bucket rate limiting, PRM verification, MoA fusion, goal decomposition, and multi-agent debate.

### 1. Implemented Components
- **Unified Gateway Server:** `cognitive/reasoning/src/core/server.ts` and `src/core/engine.ts`. Built on Hono with Web Streams API for SSE streaming.
- **Provider Adapters:** `src/providers/` (OpenAI, Anthropic, Gemini, Bedrock, Ollama, Local).
- **Resilience Engine:** `src/resilience/` (`ratelimit.ts`, `tpm.ts`, `cooldown.ts`, `budgets.ts`, `classifier.ts`).
- **Dynamic Routing:** `src/routing/` (`router.ts`, `cel.ts`, `session-affinity.ts`, `shadow.ts`).
- **Cognitive Synthesis:** `src/synthesis/moaFusion.ts` (Mixture of Agents multi-candidate synthesis), `prmVerifier.ts` (Process Reward Model step verification), and `claimDecomposer.ts`.
- **Goals & Planning:** `src/goals/goalStore.ts` (DAG task decomposition) and `src/planning/costEstimator.ts`.
- **Debate Orchestrator:** `src/debate/orchestrator.ts` (multi-model consensus and arbitration).

### 2. Missing or Incomplete Components
- Itemized 219-feature locked gateway spec from upstream `aevum_layers.zip` is not enumerated in repo docs (see `docs/GATEWAY_SPEC_AUDIT.md`), though all 51 core features and 10 roadmap extensions are implemented.

### 3. Integration Status
- Serves as the cognitive reasoning backbone. Interacts with Layer 16 Compute and Layer 18 Surfaces.
- Provides SSE streaming endpoints `/v1/chat/completions`.

### 4. Test Coverage & Evidence
- 61 test files, 311 test cases in Vitest.
- Tested via `pnpm --filter @central-intelligence/reasoning test`. All test suites pass.

### 5. Security & Operational Concerns
- API keys stored in environment variables or Infisical. SSRF filter implemented in `src/security/ssrf.ts`.

### 6. Dependencies & Blockers
- None. Runs on Node.js LTS with `@hono/node-server` and `zod`.

### 7. Completion Score & Confidence
- **Score: 87%** (Domain: 90%, Integration: 85%, Security: 85%, Testing: 85%)
- **Confidence: HIGH** (Highest engineering quality in repository).

### 8. Severity-Ranked Findings
1. **[P3] [VERIFIED] Upstream 219-Feature Checklist Missing:** Spec gap documented in `docs/GATEWAY_SPEC_AUDIT.md`.

### 9. Recommended Next Actions
- Maintain current implementation; integrate as upstream router for all Python agent invocations.

---

## Layer 5: Action & Tools Hub

- **Location:** `cognitive/action/` (233 files, 91,681 LOC, Python & TypeScript)
- **Purpose:** Agent execution runtime (Phoenix), tool sandboxing (E2B, Local Docker), Nango connector integrations, browser automation, and blast radius safety.

### 1. Implemented Components
- **Phoenix Agent Runtime:** `cognitive/action/agent/` (`builder/compiler.py`, `executor/runner.py`, `executor/deep_research.py`, `executor/agent_handoff.py`).
- **Blast Radius Simulator:** `cognitive/action/safety/blast_radius.py` (`BlastRadiusSimulator`, lines 10–65). Evaluates touched files, services, financial cost, and reversibility before execution.
- **Tool Sandbox Adapters:** `cognitive/action/agent/sandbox/e2b_adapter.py` and `local_docker_adapter.py`.
- **Connectors Hub:** `cognitive/action/connectors/` (ActivePieces patterns, Nango integration, email/slack pieces).
- **Agent API:** `cognitive/action/agent_api/` (Node.js REST API with idempotency limiters, content filtering, and event streaming).

### 2. Missing or Incomplete Components
- **E2B Sandbox Mock Return:** `cognitive/action/agent/sandbox/e2b_adapter.py#L65-L71` returns hardcoded dictionary `{"exit_code": 0, "stdout": "[E2B Simulated MicroVM ...]"}` when running in simulated mode or when `e2b` package is uninstalled. [VERIFIED: F-INT-08]
- Browser automation agent (`browser_automation/core/agent.py`) requires live Playwright browser binaries which are excluded from standard CI.

### 3. Integration Status
- Invoked by Layer 8 Orchestration.
- In `tests/integration/test_e2e_full_flow.py#L187-L194`, tool execution is validated, but operates against the E2B simulated dictionary fallback.

### 4. Test Coverage & Evidence
- 85 test files, 1,405 test cases (largest test suite in monorepo).
- Vitest connector tests (`pnpm run test:connectors`) and Python agent tests pass.

### 5. Security & Operational Concerns
- In production, if E2B credentials fail, `e2b_adapter.py` fails closed. But in non-production, commands are not truly executed, giving false confidence in agent tool behavior.

### 6. Dependencies & Blockers
- `e2b` Python package not in `requirements.lock`.

### 7. Completion Score & Confidence
- **Score: 68%** (Domain: 80%, Integration: 50%, Security: 75%, Testing: 75%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] Simulated E2B Execution in Tests:** Code execution in E2E tests returns static strings without executing code.
2. **[P2] [INFERRED] Docker Socket Exposure:** `local_docker_adapter.py` requires mounting `/var/run/docker.sock`, which presents host escalation risks.

### 9. Recommended Next Actions
- Provide a robust local container runner using non-root Podman or sandboxed WASM (e.g. Wasmtime).

---

## Layer 6: Output Generation & Multimodal Surfaces

- **Location:** `cognitive/output/` (101 files, 9,582 LOC, Python & TypeScript)
- **Purpose:** Multimodal rendering, Generative UI widgets (CopilotKit, Tiptap, Tldraw, Mermaid), document templating, C2PA watermarking, and surgical claim diff patching.

### 1. Implemented Components
- **Generative UI Adapters:** `cognitive/output/generative_ui/copilotkit_adapter.ts`, `ag_ui_adapters/tiptap_agui.ts`, and `tldraw_agui.ts`.
- **Diagrams & Canvas:** `cognitive/output/diagrams/mermaid_adapter.ts` and `canvas/tldraw_adapter.ts`.
- **Document Synthesizer:** `cognitive/output/documents/template_engine.py` (Markdown, HTML, PDF export with Jinja2-style templating).
- **Surgical Claim Diff Patcher:** `cognitive/output/integrity/claim_diff_patcher.py` (patches only refuted sentences in-place without re-streaming entire response, Feature 6.37).
- **Watermarker:** `cognitive/output/integrity/watermarker.py` (C2PA-compliant cryptographic metadata signing).
- **Citations Formatter:** `cognitive/output/citations/formatter.py`.

### 2. Missing or Incomplete Components
- Live video generation is simulated (`media_gen/core/image_route.py` uses PIL helpers).
- Voice synthesis engines use offline mock fallbacks.

### 3. Integration Status
- Serializes UI widgets to JSON schemas for rendering on Layer 18 surfaces (LibreChat / Jan).

### 4. Test Coverage & Evidence
- 29 test files, 122 test cases.
- Tested in TypeScript (`pnpm --filter @central-intelligence/output test`) and Python (`pytest cognitive/output/`).

### 5. Security & Operational Concerns
- Outbound HTML templates must prevent XSS. Escaping verified in `template_engine.py`.

### 6. Dependencies & Blockers
- None for core text/UI rendering.

### 7. Completion Score & Confidence
- **Score: 73%** (Domain: 80%, Integration: 65%, Security: 75%, Testing: 70%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [VERIFIED] Media Generation Mock:** Audio and video engines in `media_gen/` rely on PIL and mock buffers rather than real diffusion models.

### 9. Recommended Next Actions
- Connect `claim_diff_patcher.py` directly to Layer 11 Phoenix hallucination evaluator output.

---

## Layer 7: Learning, Memory & Continuous Adaptation

- **Location:** `cognitive/learning/` (69 files, 5,438 LOC)
- **Purpose:** Capability expansion through demonstration, RL routing weight adjustments, synthetic dataset generation, consent and training lineage, and skills packaging marketplace.

### 1. Implemented Components
- **Capability Expander:** `cognitive/learning/demonstration/capability_expander.py` (`CapabilityExpander`, extracts repeatable skill templates from successful multi-step execution traces).
- **RL Routing Weight Adjuster:** `cognitive/learning/rl/routing_weight_adjuster.py` (updates model provider selection weights based on user feedback).
- **Consent & Training Lineage:** `cognitive/learning/consent/consent_manager.py` and `lineage_tracker.py` (tracks user opt-in and cryptographic data lineage for model tuning).
- **Skills Packaging & Marketplace:** `cognitive/learning/skills_packaging/` (`packaging/packager.py`, `packaging/installer.py`, `marketplace/catalog.py`).
- **Synthetic Data Generator:** `cognitive/learning/synthetic/data_generator.py` and `labeling_workflow.py`.
- **Adapters:** `agenta/agenta_adapter.py`, `cognee/cognee_adapter.py`, `langmem/langmem_adapter.py`.

### 2. Missing or Incomplete Components
- Full model fine-tuning (`tuning/full_tune.py` and `tuning/peft.py`) consists of pipeline stubs without local GPU PyTorch training execution.

### 3. Integration Status
- Wires to Layer 10 c15t consent management and Layer 2 memory lesson store (`cognitive/memory/lessons/store.py`).

### 4. Test Coverage & Evidence
- 18 test files, 50 test cases.
- `skills_packaging/tests/test_skills_packaging_e2e.py` and `demonstration/tests/test_capability_expansion.py` pass.

### 5. Security & Operational Concerns
- GDPR "Right to be Forgotten" deletion propagation verified in `consent_manager.py`.

### 6. Dependencies & Blockers
- PyTorch / PEFT dependencies excluded from core lockfile (appropriate for lightweight runtime).

### 7. Completion Score & Confidence
- **Score: 65%** (Domain: 75%, Integration: 50%, Security: 75%, Testing: 65%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [INFERRED] Model Tuning Pipelines are Interface Stubs:** `tuning/peft.py` cannot execute local model weight updates without uninstalled ML libraries.

### 9. Recommended Next Actions
- Wire capability expander output directly into Layer 5 tool registry.

---

## Layer 8: Orchestration

- **Location:** `control/orchestration/` (222 files, 35,999 LOC, Python & TypeScript)
- **Purpose:** Durable multi-agent workflow execution, multi-step planning, DAG runner, ReAct execution loops, and human-in-the-loop governance.

### 1. Implemented Components
- **Multi-Step Planner & DAG Runner:** `control/orchestration/orchestrator/planner/multi_step_planner.py` and `engine/dag_runner.py` (asynchronous parallel fan-out / fan-in execution).
- **Rivet Node Graph Engine:** `control/orchestration/nodes/` (ported from Ironclad Rivet, MIT license; complete graph node execution).
- **ReAct Execution Loop:** `control/orchestration/engine/agent/reactLoop.ts`.
- **Fleet Management:** `control/orchestration/engine/fleet/paperclipAdapter.ts` and `proactiveInitiation.ts`.
- **Governance & Approvals:** `control/orchestration/governance/` (escalation gates for destructive actions).
- **Temporal Adapter:** `control/orchestration/workflow_builder/runtime/temporal_adapter.py` (`TemporalWorkflowAdapter`).

### 2. Missing or Incomplete Components
- **Temporal Server Bypass:** `temporal_adapter.py#L78` and `#L159` saves checkpoints to `./.temporal_checkpoints/<workflow_id>.json` on local disk. It does not invoke Temporal client or schedule workflows on the `temporal:7233` server container. [VERIFIED: F-INT-07]
- Hatchet distributed task queue is deferred to Phase 6 (`docs/DEFERRED_ITEMS.md#L38-L41`).

### 3. Integration Status
- Coordinates Layer 4 Reasoning, Layer 5 Action, and Layer 11 Evaluation.
- In `tests/integration/test_e2e_full_flow.py` Task 11.3, process crash survival is tested against the local disk checkpoint file.

### 4. Test Coverage & Evidence
- 23 test files, 99 test cases.
- `pnpm run test:orchestration` passes scenario tests. `tests/integration/test_compose_stack_e2e.py#L154-L199` exercises live Temporal container separately.

### 5. Security & Operational Concerns
- Local file checkpoints (`./.temporal_checkpoints`) are lost if a container is destroyed without a persistent volume mount, violating durable workflow guarantees.

### 6. Dependencies & Blockers
- `temporalio` Python client is installed in lockfile, but `TemporalWorkflowAdapter` fails to utilize it.

### 7. Completion Score & Confidence
- **Score: 70%** (Domain: 80%, Integration: 50%, Security: 75%, Testing: 70%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] Temporal Workflow Checkpointing Bypasses Temporal Daemon:** `temporal_adapter.py` operates as a local JSON file store rather than a distributed workflow client.

### 9. Recommended Next Actions
- Rewrite `TemporalWorkflowAdapter` to execute workflows via `temporalio.client.Client.start_workflow()`.

---

# Plane 2: Control & Safety Plane (Layers 9–14)

---

## Layer 9: Context Engineering

- **Location:** `control/context/` (30 files, 4,660 LOC)
- **Purpose:** Context assembly, token budgeting, prompt layering, context compaction, cache prefix optimization, and dual-boundary prompt injection defense.

### 1. Implemented Components
- **Dual-Boundary Context Assembler:** `control/context/trust/boundary_assembler.py` (`DualBoundaryAssembler`, lines 27–135). Segregates system instructions from untrusted user/tool/memory data.
- **Injection Detector:** `control/context/trust/injection_detector.py` (`InjectionDetector`). Scans for system override patterns, instruction ignores, and role-playing attacks.
- **Untrusted Sandbox:** `control/context/trust/untrusted_sandbox.py` (`UntrustedBlock`, escapes `</untrusted_content>` delimiters).
- **Context Compactor:** `control/context/compaction/` and `assembly/context_assembler.py`.
- **Cache Optimizer:** `control/context/cache/prefix_optimizer.py`.
- **FastAPI Service:** `control/context/server.py` (`/v1/context/assemble`).

### 2. Missing or Incomplete Components
- Tag attribute mismatch: Code outputs `<untrusted_content source="..." trust="...">`, whereas `docs/SECURITY_REVIEW.md#L73` claims cryptographic `<untrusted_user_input hash="...">`. [VERIFIED: F-DOC-01]

### 3. Integration Status
- Wires directly into Layer 4 Reasoning and Layer 10 Safety.

### 4. Test Coverage & Evidence
- 9 test files, 24 test cases.
- `control/context/tests/test_boundary_assembler.py` and `test_context_assembler.py` pass.

### 5. Security & Operational Concerns
- Regex-based injection detection can be bypassed by novel encoding or multilingual obfuscation; requires pairing with NeMo Guardrails.

### 6. Dependencies & Blockers
- None. Fully self-contained.

### 7. Completion Score & Confidence
- **Score: 82%** (Domain: 85%, Integration: 75%, Security: 90%, Testing: 75%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [VERIFIED] Documentation Tag Mismatch:** Docs specify `<untrusted_user_input>` with hash, code emits `<untrusted_content>`.

### 9. Recommended Next Actions
- Synchronize documentation with actual `<untrusted_content>` schema.

---

## Layer 10: Safety, Trust & Privacy

- **Location:** `control/safety/` (102 files, 13,029 LOC)
- **Purpose:** 4-Tier PII scrubbing, NeMo Guardrails safety policies, c15t consent management, minor protections, and the cryptographic Unified Merkle Audit Ledger.

### 1. Implemented Components
- **Unified Merkle Audit Ledger:** `control/safety/audit/ledger.py` (`UnifiedAuditLedger`, lines 30–413). SQLite-backed append-only ledger with SHA-256 hash chaining and full binary Merkle tree root calculation (`get_merkle_root()`).
- **4-Tier PII Scrubber:** `control/safety/pii/tier_scrubber.py` (`FourTierPIIScrubber`), `detectors.py`, and `redactors.py` (redacts emails, phones, SSNs, API keys, and IP addresses into tokenized surrogates).
- **Guardrails Adapter:** `control/safety/guardrails/nemo/nemo_adapter.py` (`NeMoGuardrailsAdapter`).
- **Consent Adapter:** `control/safety/consent/c15t_adapter.py` (`C15tConsentAdapter`).
- **Production Guard:** `control/safety/production_guard.py` (`is_production`, `require_live_adapter`, `fail_closed_in_production`).
- **Wellbeing:** `control/safety/wellbeing/minor_safeguards.py` and `rights/content_rights.py`.

### 2. Missing or Incomplete Components
- **Fatal Production Guard Defect:** `production_guard.py#L30-L32` checks `os.getenv("ENVIRONMENT", "").strip().lower() == "production"`. But `docs/DEPLOYMENT.md#L33` instructs operators to set `ENV=production`. If `ENV=production` is used, `is_production()` evaluates to `False`, allowing simulated adapters to run silently. [VERIFIED: F-SEC-01]
- **Uncalled Fail-Closed Guards:** 19 out of 33 adapter files import `fail_closed_in_production` but never invoke it. [VERIFIED: F-SEC-02]
- NeMo Guardrails uses local regex/heuristic fallbacks rather than a live NeMo server daemon.

### 3. Integration Status
- Wires to Layer 2 Memory, Layer 9 Context, Layer 12 Identity, and Layer 14 Observability.
- Merkle ledger verified in `tests/integration/test_e2e_full_flow.py#L270-L286`.

### 4. Test Coverage & Evidence
- 22 test files, 148 test cases.
- PII scrubbing, Merkle hashing, and tamper detection tests pass.

### 5. Security & Operational Concerns
- The `ENV` vs `ENVIRONMENT` defect is a critical security vulnerability that defeats the primary production guard mechanism.

### 6. Dependencies & Blockers
- None.

### 7. Completion Score & Confidence
- **Score: 77%** (Domain: 85%, Integration: 60%, Security: 85%, Testing: 80%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] Production Guard Bypass via Variable Mismatch:** `production_guard.py#L30-L32` ignores `ENV=production`.
2. **[P1] [VERIFIED] Dead Import of `fail_closed_in_production`:** Over 57% of adapters import the guard but never execute it.

### 9. Recommended Next Actions
- Fix `production_guard.py#L31` to accept both: `os.getenv("ENVIRONMENT", os.getenv("ENV", ""))`.
- Wire `fail_closed_in_production()` across all 19 non-compliant adapters.

---

## Layer 11: Evaluation & Quality

- **Location:** `control/evaluation/` (63 files, 8,678 LOC, Python & Go)
- **Purpose:** Continuous evaluation, hallucination detection, drift monitoring, multi-agent simulation, and Arize Phoenix / Langfuse integration.

### 1. Implemented Components
- **Phoenix Adapter:** `control/evaluation/phoenix/phoenix_adapter.py` (`PhoenixAdapter`, lines 106–269). Decomposes responses into atomic claims and evaluates keyword grounding against retrieved context.
- **Langfuse Fanout Gateway:** `control/evaluation/langfuse/` (`main.go`, Go module proxying traces to central and tenant Langfuse projects).
- **Simulation Runner:** `control/evaluation/simulation/scenario_runner.py` and `sandbox/tenant_sandbox.py`.
- **Drift & Accuracy Scoring:** `control/evaluation/accuracy/` and `phoenix_adapter.py` (`calculate_embedding_drift`).

### 2. Missing or Incomplete Components
- **Disconnected Phoenix Client:** `phoenix_adapter.py` never makes HTTP calls to `http://localhost:6006`. It evaluates hallucination using an in-memory string-splitting heuristic. [VERIFIED]
- `pyproject.toml#L95` explicitly disables Phoenix in test runs (`addopts = "-p no:phoenix"`).

### 3. Integration Status
- Provides accuracy scores consumed by Layer 8 Orchestration (`maybeTriggerSecondOpinion`).

### 4. Test Coverage & Evidence
- 16 test files, 46 test cases. Tests validate heuristic claim scoring in RAM.

### 5. Security & Operational Concerns
- Hallucination scoring is a basic string overlap heuristic, not a true semantic cross-encoder or LLM-as-a-judge model.

### 6. Dependencies & Blockers
- Live Phoenix server in `docker-compose.yml` is Elastic-2.0 licensed (`profiles: ["self-hosted-non-osi"]`).

### 7. Completion Score & Confidence
- **Score: 60%** (Domain: 70%, Integration: 40%, Security: 70%, Testing: 65%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] Phoenix Adapter is In-Memory Heuristic:** Does not connect to live Phoenix container.
2. **[P2] [VERIFIED] Phoenix Pytest Plugin Suppressed:** Disabled via `-p no:phoenix` in `pyproject.toml`.

### 9. Recommended Next Actions
- Implement real HTTP/REST export in `phoenix_adapter.py` to Arize Phoenix or OpenTelemetry collector.

---

## Layer 12: Identity & Access Management (IAM)

- **Location:** `control/identity/` (26 files, 3,186 LOC)
- **Purpose:** Multi-tenant organization hierarchies, Keycloak OIDC/OAuth 2.1, Google Zanzibar ReBAC (OpenFGA), and secret vaulting (Infisical).

### 1. Implemented Components
- **Keycloak Adapter:** `control/identity/keycloak_adapter.py` (`KeycloakAdapter`, lines 83–395). Password strength validation, PBKDF2/SHA-256 password hashing, token issuance, and TOTP verification.
- **OpenFGA Adapter:** `control/identity/openfga_adapter.py` (`OpenFGAAdapter`, lines 54–244). Relationship tuple checking, document hierarchies (`can_view`, `can_edit`), memory access, and delegation grants.
- **Infisical Secret Vault:** `control/identity/secrets/infisical_adapter.py` (`InfisicalAdapter`, lines 65–237). Secret scoping by tenant/app, versioned history, zero-downtime rotation, and audit logging.

### 2. Missing or Incomplete Components
- **OpenFGA Adapter Never Issues Network Calls:** `openfga_adapter.py#L69-L73` stores all relationship tuples in an in-memory `Set[Tuple[str, str, str]]`. It has zero HTTP/gRPC calls to the live `openfga:8081` container. [VERIFIED: F-INT-01]
- **Infisical Adapter Stores Secrets Plaintext in RAM:** `infisical_adapter.py#L85` stores all secrets in `self._vault = {}`. It has zero HTTP calls to Infisical KMS (`:8083`). [VERIFIED: F-INT-02]
- **Keycloak Adapter Operates in RAM:** `keycloak_adapter.py#L106-L111` manages user registration and authentication against Python dictionaries `_users` and `_usernames`. The only HTTP call is an optional TOTP check if an env var is set. [VERIFIED]

### 3. Integration Status
- Wires to Layer 2 Memory (`openfga_bridge.py`) and Layer 3 Knowledge (`openfga_bridge.py`).
- All integrations succeed in tests because they assert against shared in-memory dictionary state.

### 4. Test Coverage & Evidence
- 11 test files, 23 test cases. All tests pass against in-memory emulators.

### 5. Security & Operational Concerns
- **Critical Data Loss:** On process crash or container restart, all registered users, active tokens, ReBAC permissions, and vaulted secrets are permanently wiped.
- **Plaintext Secret Exposure:** Vault secrets reside unencrypted in Python heap memory.

### 6. Dependencies & Blockers
- None for in-memory emulation; live mode requires wiring HTTP clients.

### 7. Completion Score & Confidence
- **Score: 45%** (Domain: 65%, Integration: 25%, Security: 40%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] OpenFGA Adapter Completely Bypasses OpenFGA Service:** ReBAC is an ephemeral Python set; no container interaction.
2. **[P0] [VERIFIED] Infisical Vault is an In-Memory Dictionary:** Plaintext secrets stored in RAM; wiped on process death.
3. **[P0] [VERIFIED] Keycloak Adapter is an In-Memory User Store:** Ignores live Keycloak container for user auth and tokens.

### 9. Recommended Next Actions
- Replace in-memory dictionaries in `OpenFGAAdapter` with live HTTP REST/gRPC client to `http://openfga:8081`.
- Replace `self._vault` in `InfisicalAdapter` with real Infisical SDK / REST API calls.
- Connect `KeycloakAdapter` to Keycloak OIDC discovery and token endpoints.

---

## Layer 13: Entitlements & Billing

- **Location:** `control/billing/` (31 files, 3,145 LOC)
- **Purpose:** Token metering (OpenMeter), AGPL-quarantined billing and subscriptions (Lago), payment orchestration (Hyperswitch), and BYOK policies.

### 1. Implemented Components
- **OpenMeter Adapter:** `control/billing/metering/openmeter_adapter.py` (`OpenMeterAdapter`, lines 27–162). CloudEvents 1.0 JSON payload schema, per-app breakdown, and token usage tracking.
- **Lago Adapter:** `control/billing/engine/lago_adapter.py` (`LagoAdapter`, lines 59–236). Subscription tiers (Free, Pro, Enterprise), monthly quotas, and invoice generation.
- **Hyperswitch Adapter:** `control/billing/payments/hyperswitch_adapter.py` (`HyperswitchAdapter`, lines 80–253). Payment intent creation, payment methods, and invoice settlement.

### 2. Missing or Incomplete Components
- **Lago Adapter Never Sends HTTP Requests:** `lago_adapter.py#L19` imports `httpx` but never uses it. All plan checks, quota enforcement, and invoice generations execute against in-memory dictionaries (`_plans`, `_subscriptions`). [VERIFIED: F-INT-03]
- **OpenMeter Usage Queries Ignore Remote Server:** `openmeter_adapter.py#L111` implements `query_usage` strictly against local in-memory list `self._local_events`. [VERIFIED]
- **Hyperswitch Catches Exceptions Silently:** `hyperswitch_adapter.py#L140-L159` attempts an HTTP call with a 100ms timeout, catches all exceptions with `pass`, and marks payment as succeeded in memory. [VERIFIED: F-INT-04]

### 3. Integration Status
- Wires to Layer 4 Reasoning for token consumption reporting.
- Lago is quarantined on `agpl_quarantine_net` in Docker Compose, but Python adapter does not communicate with it.

### 4. Test Coverage & Evidence
- 9 test files, 32 test cases. Tests pass against in-memory dictionaries.

### 5. Security & Operational Concerns
- Swallowing payment exceptions allows uncharged or failed transactions to be recorded as successful.
- Process restart resets all customer monthly usage counters to zero.

### 6. Dependencies & Blockers
- None.

### 7. Completion Score & Confidence
- **Score: 46%** (Domain: 65%, Integration: 30%, Security: 40%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] Lago Billing Engine is 100% In-Memory Simulation:** Imports `httpx` without issuing requests.
2. **[P0] [VERIFIED] Silent Exception Swallowing in Hyperswitch Adapter:** Payment failures fall back to in-memory success.
3. **[P1] [VERIFIED] OpenMeter Adapter Queries In-Memory Buffer Only:** Remote OpenMeter container state is ignored.

### 9. Recommended Next Actions
- Wire `lago_adapter.py` to issue authenticated HTTP requests to `http://lago:3000`.
- Remove `except Exception: pass` in `hyperswitch_adapter.py`; raise `PaymentProcessingError` and call `fail_closed_in_production()`.

---

## Layer 14: Observability

- **Location:** `control/observability/` (34 files, 3,271 LOC)
- **Purpose:** Distributed tracing, latency percentiles, error rate monitoring, SigNoz OpenTelemetry collectors, PostHog product analytics, and Uptime Kuma heartbeats.

### 1. Implemented Components
- **SigNoz Adapter:** `control/observability/signoz/signoz_adapter.py` (`SigNozAdapter`, lines 31–200). Span hierarchy (root/child), metric recording, P50/P90/P95/P99 latency calculations, and request replay metadata.
- **PostHog Adapter:** `control/observability/posthog/posthog_adapter.py` (`PostHogAdapter`). Event capture and user identification with HTTP client.
- **Uptime Kuma Adapter:** `control/observability/uptime/uptime_kuma_adapter.py` (`UptimeKumaAdapter`). Push heartbeats with HTTP client.

### 2. Missing or Incomplete Components
- **SigNoz Adapter Never Exports OTLP Data:** `signoz_adapter.py#L15` imports `httpx` and line 24 imports `fail_closed_in_production`, but neither is ever called. Spans and metrics are stored strictly in `self._spans: List[SpanRecord] = []` in Python memory. No OTLP data is exported to `signoz:4317`. [VERIFIED: F-INT-05]
- Neither `posthog_adapter.py` nor `uptime_kuma_adapter.py` calls `fail_closed_in_production()`.

### 3. Integration Status
- Wires to Layer 10 PII Scrubber (Tier 1 Telemetry Sink). Spans are scrubbed before appending to in-memory list.

### 4. Test Coverage & Evidence
- 9 test files, 38 test cases. Percentile calculations and span parentage verified in unit tests.

### 5. Security & Operational Concerns
- Memory leak risk: In-memory span and metric lists grow unbounded during long-running server sessions.
- In production, SigNoz dashboards will display zero traces or metrics.

### 6. Dependencies & Blockers
- OpenTelemetry Python SDK (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`) is not utilized by `SigNozAdapter`.

### 7. Completion Score & Confidence
- **Score: 48%** (Domain: 65%, Integration: 25%, Security: 60%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] SigNoz Adapter Has No OTLP Exporter:** Appends spans to Python RAM list; dead imports of `httpx` and `fail_closed_in_production`.
2. **[P1] [VERIFIED] Unbounded In-Memory Span Growth:** `_spans` list is never pruned or flushed.

### 9. Recommended Next Actions
- Integrate standard `opentelemetry-exporter-otlp` to export spans to `http://signoz:4317`.

---

# Plane 3: Platform Infrastructure Plane (Layers 15–17)

---

## Layer 15: Data & Messaging

- **Location:** `platform_infra/data/` (41 files, 3,234 LOC)
- **Purpose:** Relational storage, pgvector semantic search, Apache AGE graph querying, Dragonfly / Valkey in-memory caching, and AutoMQ Kafka event streaming.

### 1. Implemented Components
- **Dragonfly Adapter:** `platform_infra/data/cache/dragonfly_adapter.py` (`DragonflyAdapter`, lines 40–241). Real Redis client connection with ping, get/set/del/mget/mset, pub/sub, and fail-closed verification in production.
- **AutoMQ Streaming Adapter:** `platform_infra/data/messaging/automq_adapter.py` (`AutoMQAdapter`, lines 76–261). Schema versioning, partition/offset tracking, DLQ routing, and fail-closed checks if `confluent-kafka` is missing.
- **Event Bus:** `platform_infra/data/messaging/event_bus.py`.
- **Supabase Adapter:** `platform_infra/data/supabase/supabase_adapter.py` (`SupabaseAdapter`, lines 49–261).

### 2. Missing or Incomplete Components
- **Supabase Adapter Does Not Connect to PostgreSQL:** `supabase_adapter.py#L57-L65` stores tables in `self.tables = {}`, vectors in `self.vector_collections = {}`, and graphs in `self.graphs = {}`. It computes cosine similarity using pure Python math and evaluates RLS via Python dictionary lookups. It never issues SQL statements. [VERIFIED: F-INT-06]
- `docs/SECURITY_REVIEW.md#L81` claims `platform_infra/data/supabase/` uses parameterized queries with asyncpg/Postgres `%s` bindings. This claim is factually false. [VERIFIED]

### 3. Integration Status
- Dragonfly adapter validated against live Valkey container in CI (`tests/integration/test_compose_stack_e2e.py#L102-L116`).
- AutoMQ requires uninstalled `confluent-kafka` in live mode.

### 4. Test Coverage & Evidence
- 12 test files, 25 test cases. Dragonfly and in-memory Supabase tests pass.

### 5. Security & Operational Concerns
- Supabase adapter's in-memory data structures are wiped on process restart. RLS is enforced only at the Python dictionary level, not by database engine policies.

### 6. Dependencies & Blockers
- `confluent-kafka` missing from lockfile.

### 7. Completion Score & Confidence
- **Score: 54%** (Domain: 65%, Integration: 45%, Security: 55%, Testing: 55%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] Supabase Adapter is Pure In-Memory Dictionary:** No SQL or connection to PostgreSQL container.
2. **[P1] [VERIFIED] Documentation Inaccuracy:** `SECURITY_REVIEW.md` claims asyncpg parameterized queries exist in Supabase adapter where none exist.

### 9. Recommended Next Actions
- Replace in-memory dictionaries in `SupabaseAdapter` with real `asyncpg` or `pg8000` database connections.

---

## Layer 16: Compute & Model Serving

- **Location:** `platform_infra/compute/` (38 files, 2,471 LOC)
- **Purpose:** Carbon-aware routing, hardware tiering, model cataloging, zero-downtime hot-swapping, provider health monitoring, and safe physical actuation.

### 1. Implemented Components
- **Carbon-Aware Router:** `platform_infra/compute/energy/carbon_router.py` (`CarbonAwareRouter`, routes requests to compute regions with lowest carbon intensity $gCO_2/kWh$).
- **Hardware Tierer:** `platform_infra/compute/dispatcher/hardware_tierer.py` (tiers tasks across CPU, GPU, TPU, and NPU based on latency/compute requirements).
- **Model Hot-Swap Engine:** `platform_infra/compute/lifecycle/hot_swap.py` (`ModelHotSwapEngine`, manages transition phases without dropped connections).
- **Provider Health Monitor:** `platform_infra/compute/health/provider_health.py` (circuit breaker with sliding error window).
- **Device Control:** `platform_infra/compute/actuation/device_control.py` (physical IoT actuation with safety limit clamping).

### 2. Missing or Incomplete Components
- Carbon intensity data and hardware device metrics are driven by synthetic models.
- Actuation is simulated via safety clamp envelopes.

### 3. Integration Status
- Wires to Layer 4 Reasoning to provide provider health and routing recommendations.

### 4. Test Coverage & Evidence
- 10 test files, 26 test cases. All unit tests pass.

### 5. Security & Operational Concerns
- Actuation safety clamp prevents dangerous commands, but hardware integration is mock-only.

### 6. Dependencies & Blockers
- None.

### 7. Completion Score & Confidence
- **Score: 53%** (Domain: 65%, Integration: 35%, Security: 70%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [INFERRED] Synthetic Carbon & Hardware Data:** Regional carbon metrics and hardware stats are simulated.

### 9. Recommended Next Actions
- Connect `CarbonAwareRouter` to live grid carbon intensity APIs (e.g., ElectricityMaps).

---

## Layer 17: Release & Lifecycle

- **Location:** `platform_infra/release/` (43 files, 2,415 LOC)
- **Purpose:** Zero-downtime rolling deployments (Kamal), database schema migration gates (Bytebase), feature flags (GrowthBook), and canary release analysis.

### 1. Implemented Components
- **GrowthBook Adapter:** `platform_infra/release/flags/growthbook_adapter.py` (`GrowthBookAdapter`, feature flags and experiment targeting with fail-closed checks).
- **Coolify Adapter:** `platform_infra/release/paas/coolify_adapter.py` (`CoolifyAdapter`, PaaS deployment management).
- **Canary Manager:** `platform_infra/release/canary/canary_manager.py` (canary percentages and rollback triggers).
- **Release Gates:** `platform_infra/release/gates/release_gate.py` (evaluates test pass rates, security scans, and latency thresholds).
- **Kamal Adapter:** `platform_infra/release/ci/kamal_adapter.py` (`KamalAdapter`).
- **Bytebase Adapter:** `platform_infra/release/db/bytebase_adapter.py` (`BytebaseAdapter`).

### 2. Missing or Incomplete Components
- **Kamal Adapter is a Synthetic State Machine:** `kamal_adapter.py#L90-L120` does not invoke the `kamal` CLI binary or Docker engine. It sequences strings in an in-memory list `phases_completed` and returns `zero_downtime_guaranteed = True`. [VERIFIED: F-OPS-01]
- **Bytebase Adapter Does Not Run Migrations:** `bytebase_adapter.py#L128-L137` splits SQL strings on semicolon and stores them in memory. It does not connect to Bytebase API or run DDL against PostgreSQL/SQLite. [VERIFIED: F-OPS-02]
- Both `kamal_adapter.py` and `bytebase_adapter.py` import `fail_closed_in_production` but never call it. [VERIFIED: F-SEC-02]

### 3. Integration Status
- Documented in `docs/DEPLOYMENT.md#L90` and `#L117` as the core deployment and migration pipeline, but exists only as simulated models.

### 4. Test Coverage & Evidence
- 12 test files, 19 test cases.
- `tests/integration/test_live_adapters.py#L508-L515` tests Kamal by asserting `dep.phase.value == "completed"` immediately.

### 5. Security & Operational Concerns
- Relying on `kamal_adapter.py` or `bytebase_adapter.py` for actual production deployments or database migrations will result in zero operations being executed.

### 6. Dependencies & Blockers
- External `kamal` binary and Bytebase API integration not wired.

### 7. Completion Score & Confidence
- **Score: 50%** (Domain: 65%, Integration: 30%, Security: 60%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P0] [VERIFIED] Kamal Deployment Adapter Does Not Deploy:** Purely in-memory string sequencer; does not execute Kamal or Docker.
2. **[P0] [VERIFIED] Bytebase Migration Adapter Does Not Execute DDL:** Splits SQL strings in RAM; no database connectivity.

### 9. Recommended Next Actions
- Replace synthetic models with shell execution wrappers or actual REST integrations to Bytebase and Kamal.

---

# Plane 4: Surface & Federation Plane (Layers 18–19)

---

## Layer 18: Interaction

- **Location:** `surface/interaction/` (44 files, 2,119 LOC)
- **Purpose:** Cross-platform client interaction across Web (LibreChat), Desktop (Jan), CLI Terminal (OpenCode), and IDE (Zed), unified via the Universal Surface Adapter.

### 1. Implemented Components
- **Universal Surface Adapter:** `surface/interaction/universal/surface_adapter.py` (`UniversalSurfaceAdapter`, coordinates session state across clients).
- **Continuity Engine:** `surface/interaction/continuity/continuity_engine.py` (handoff of active conversational context between devices).
- **Terminal Adapter:** `surface/interaction/terminal/opencode_adapter.ts` (CLI terminal interface).
- **IDE Adapter:** `surface/interaction/ide/zed_adapter.ts` (Zed editor integration).
- **Ambient & Nudge:** `surface/interaction/ambient/ambient_mode.py` and `proactive/nudge_engine.py`.
- **LibreChat Adapter:** `surface/interaction/web/librechat_adapter.py` (`LibreChatAdapter`, lines 46–122).
- **Jan Desktop Adapter:** `surface/interaction/desktop/jan_adapter.py` (`JanDesktopAdapter`, lines 40–105).

### 2. Missing or Incomplete Components
- **LibreChat Adapter is an In-Memory Session Dictionary:** `librechat_adapter.py` has no HTTP calls or WebSocket listeners connecting to the `librechat:3080` container. It stores `ChatMessage` dataclasses in a local Python dict `_conversations`. [VERIFIED]
- **Jan Desktop Adapter is In-Memory String Formatter:** `jan_adapter.py#L92` returns `"[Jan Local llama-3.2-3b-instruct-q4] Response for: ..."`. It does not connect to Jan or Nitro desktop processes. [VERIFIED]
- Both adapters import `fail_closed_in_production` but never call it. [VERIFIED: F-SEC-02]

### 3. Integration Status
- Acts as top-of-stack entry point for user instructions.
- In `tests/integration/test_e2e_full_flow.py#L137-L145` and `tests/load/test_load_chat.py`, chat turns execute entirely within `LibreChatAdapter`'s in-memory dictionary.

### 4. Test Coverage & Evidence
- 10 test files, 17 test cases.
- OpenCode and Zed tested via `node ... --test`. Load test runs 1,000 requests against in-memory dictionary in <0.5s.

### 5. Security & Operational Concerns
- The chat frontend cannot reach the backend in live environments because the bridge is an in-memory Python structure rather than an HTTP proxy or API gateway.

### 6. Dependencies & Blockers
- None for in-memory structures; live operation requires wiring API endpoints.

### 7. Completion Score & Confidence
- **Score: 50%** (Domain: 60%, Integration: 30%, Security: 65%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P1] [VERIFIED] LibreChat Web Adapter is In-Memory Mock:** Does not connect to LibreChat container.
2. **[P1] [VERIFIED] Jan Desktop Adapter is In-Memory String Formatter:** Does not connect to on-device engine.

### 9. Recommended Next Actions
- Build an API bridge exposing Central Intelligence endpoints to LibreChat via OpenAI-compatible endpoints on Layer 4 Model Gateway (`cognitive/reasoning/`).

---

## Layer 19: Specialization & Federation

- **Location:** `surface/federation/` (32 files, 1,771 LOC)
- **Purpose:** Domain-specialized cognitive brains, Huly project management integration, differential privacy federated learning, and Federated Brain Sync Protocol.

### 1. Implemented Components
- **Huly Project Management Adapter:** `surface/federation/pm/huly_adapter.py` (`HulyAdapter`, lines 58–172). Task creation, assignment, status tracking, and webhooks with real `httpx` client logic and fail-closed checks.
- **Federated Brain Sync:** `surface/federation/sync/federated_sync.py` (`FederatedBrainSyncProtocol`, Crown Jewel 19.04, 19.12–19.16).
- **Conflict Resolution:** `surface/federation/sync/conflict_resolver.py` (vector clocks and timestamp reconciliation).
- **Consent Gate:** `surface/federation/sync/consent_gate.py` (verifies tenant consent before syncing memory records).
- **Brain Factory:** `surface/federation/brain/brain_factory.py` (instantiates specialized personas for Legal, Medical, and Coding domains).
- **Federated Learning:** `surface/federation/learning/federated_learning.py` (differential privacy noise injection and gradient aggregation simulation).

### 2. Missing or Incomplete Components
- In `tests/integration/test_e2e_full_flow.py#L298-L300`, Huly integration test mocks `httpx.post`.
- Federated learning and brain sync operate over local memory buffers rather than a decentralized network transport (e.g. libp2p or gRPC).

### 3. Integration Status
- Wires to Layer 8 Orchestration for task creation.
- Interacts with Layer 2 Memory for cross-agent memory sharing.

### 4. Test Coverage & Evidence
- 7 test files, 12 test cases.
- All tests pass against local mock fixtures.

### 5. Security & Operational Concerns
- Federated sync includes differential privacy Laplace noise addition, protecting individual record values.

### 6. Dependencies & Blockers
- None.

### 7. Completion Score & Confidence
- **Score: 54%** (Domain: 65%, Integration: 35%, Security: 70%, Testing: 50%)
- **Confidence: HIGH**

### 8. Severity-Ranked Findings
1. **[P2] [VERIFIED] Federated Sync Lacks Network Transport:** Brain synchronization runs in-process without network peer discovery.

### 9. Recommended Next Actions
- Wire `HulyAdapter` to live Huly front-end container in `docker-compose.yml`.
