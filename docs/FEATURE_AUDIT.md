# Feature Audit — L1 through L8

> **Spec Source:** `aevum_layers.zip` (`aevum_layers/Layer_01_Perception.md` through `aevum_layers/Layer_08_Orchestration.md`, `Appendix_A_Packs.md`, `Appendix_B_Mapping.md`)  
> **Repository Audited:** `d:\central-intelligence` (`main` + Task 2 working-tree hardening)  
> **Scope:** 337 core cognitive & orchestration features across Layers 1–8 (`1.01`–`8.50`), plus cross-reference note for the 219-feature locked gateway spec referenced in Layer 4 (see [`docs/GATEWAY_SPEC_AUDIT.md`](GATEWAY_SPEC_AUDIT.md)).

## Legend & Status Criteria

| Symbol | Status | Definition |
|---|---|---|
| ✅ | **Built** | Concrete implementation verified on disk with domain logic and unit/integration coverage; external-service adapters include Task 2 `live`/`simulated` mode labeling and production guards where applicable. |
| ⚠️ | **Partial or Stub** | Interface, heuristic, synthetic generator, subset implementation, or offline-fallback adapter exists, but lacks full capability depth or requires an external provider/hardware backend not implemented in-repo. |
| ❌ | **Missing** | No dedicated implementation found across L1–L8 (or sibling layers) in `d:\central-intelligence`. |
| 📦 | **Deferred / Cross-Layer** | Intentionally deferred past v1 (`8.31`), moved to domain/product packs (`Appendix_A_Packs.md`), or primarily owned by a sibling layer (`control/` / `surface/` / `platform_infra/`) with integration hooks. |

## Summary Rollup (L1–L8)

| Layer | Spec File | Total Features | ✅ Built | ⚠️ Partial / Stub | ❌ Missing | 📦 Deferred / Cross-Layer |
|---|---|---:|---:|---:|---:|---:|
| **L1 Perception** | `Layer_01_Perception.md` | 47 | 20 | 12 | 15 | 0 |
| **L2 Memory** | `Layer_02_Memory.md` | 51 | 44 | 7 | 0 | 0 |
| **L3 Knowledge** | `Layer_03_Knowledge.md` | 46 | 30 | 9 | 7 | 0 |
| **L4 Reasoning & Planning** | `Layer_04_Reasoning_Planning.md` (+219 gateway note) | 27 | 22 | 5 | 0 | 0 |
| **L5 Action & Tools** | `Layer_05_Action_Tools.md` | 47 | 37 | 8 | 2 | 0 |
| **L6 Output** | `Layer_06_Output.md` | 40 | 22 | 10 | 8 | 0 |
| **L7 Learning & Adaptation** | `Layer_07_Learning_Adaptation.md` | 29 | 19 | 4 | 6 | 0 |
| **L8 Orchestration** | `Layer_08_Orchestration.md` | 50 | 40 | 9 | 0 | 1 |
| **Total (L1–L8)** | **8 layer specs** | **337** | **234** | **64** | **38** | **1** |

---

## L1 Perception (47 features)

> Primary implementation root: `cognitive/perception/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 1.01 | Text (plain, markdown, rich text) | ✅ Built | `cognitive/perception/normalize/event_queue.py`, `cognitive/perception/document/unstructured_adapter.py` | Normalizes plain/text events and document elements |
| 1.02 | Images (common formats, including HEIC, SVG, TIFF) | ⚠️ Partial | `cognitive/perception/vision/vlm_client.py`, `cognitive/perception/vision/paddleocr_adapter.py` | PNG/JPEG/PIL handled; VLM uses Gateway in `live` mode; HEIC/SVG/TIFF decoders not explicitly wired |
| 1.03 | Audio (common formats) | ✅ Built | `cognitive/perception/audio/handy_adapter.py`, `cognitive/perception/audio/livekit_adapter.py` | Byte/file ingestion + WebRTC `AudioChunk` streaming |
| 1.04 | Video | ⚠️ Partial | `cognitive/perception/audio/livekit_adapter.py` | LiveKit WebRTC session scaffold exists; dedicated video frame/temporal analyzer missing |
| 1.05 | Documents (text-based and scanned PDF, office formats) | ✅ Built | `cognitive/perception/document/unstructured_adapter.py`, `cognitive/perception/vision/paddleocr_adapter.py` | Unstructured partitioning + PaddleOCR fallback for scanned docs |
| 1.06 | Structured data (JSON, XML, tabular) | ✅ Built | `cognitive/perception/document/unstructured_adapter.py`, `cognitive/perception/normalize/event_queue.py` | Parsed document elements and normalized structured payloads |
| 1.07 | Source code with syntax awareness | ⚠️ Partial | `cognitive/perception/normalize/event_queue.py` | Handled as text events; AST/syntax-aware code perception relies on L3/L4 tooling |
| 1.08 | Live streams and sensor data | ⚠️ Partial | `cognitive/perception/audio/livekit_adapter.py`, `cognitive/perception/normalize/event_queue.py` | WebRTC audio streaming present; generic hardware sensor ingestion not implemented |
| 1.09 | Screen and interface state: screenshots, UI element tree *(new)* | ⚠️ Partial | `cognitive/perception/screen/screenpipe_adapter.py` | Screenpipe OCR frames implemented (`live`/`simulated`); UI accessibility element-tree extraction missing |
| 1.10 | Rendered web page capture *(new)* | ✅ Built | `cognitive/perception/document/crawl4ai_adapter.py` | Crawl4AI adapter with HTML/Markdown extraction and offline HTTP fallback |
| 1.11 | Printed text extraction | ✅ Built | `cognitive/perception/vision/paddleocr_adapter.py`, `cognitive/perception/document/unstructured_adapter.py` | PaddleOCR `extract_text_from_image` |
| 1.12 | Handwriting recognition | ❌ Missing | — | No handwriting-specific OCR recognizer or test |
| 1.13 | Multi-language text (100+ languages) | ✅ Built | `cognitive/perception/translation/core/detector.py`, `cognitive/perception/translation/core/engine.py`, `cognitive/perception/vision/paddleocr_adapter.py` | `LocaleDetector` + translation pipeline + multilingual OCR config |
| 1.14 | Table extraction into rows and columns | ⚠️ Partial | `cognitive/perception/document/unstructured_adapter.py` | Unstructured element classification includes tables when live library installed; fallback produces text blocks |
| 1.15 | Form field extraction (key-value pairs) | ❌ Missing | — | No dedicated key-value form parser in `cognitive/perception/` |
| 1.16 | Layout-aware parsing (headings, sections, reading order) | ✅ Built | `cognitive/perception/document/unstructured_adapter.py` | Partitioning into typed `DocumentElement`s (`Title`, `NarrativeText`, etc.) |
| 1.17 | Formula recognition with LaTeX output | ❌ Missing | — | No math/LaTeX OCR extractor |
| 1.18 | Chart and graph data extraction | ⚠️ Partial | `cognitive/perception/vision/vlm_client.py` | Achievable only via VLM prompt in `live` mode; no dedicated chart parser |
| 1.19 | Signature and stamp detection | ❌ Missing | — | No signature/stamp detector |
| 1.20 | Parallel batch processing of documents | ❌ Missing | — | Single-document/URL APIs in `UnstructuredAdapter`/`Crawl4AIAdapter`; batch scheduler missing in L1 |
| 1.21 | Real-time streaming transcription | ✅ Built | `cognitive/perception/audio/livekit_adapter.py`, `cognitive/perception/voice_speech/duplex/voice_session_runner.py` | LiveKit audio chunks + duplex session runner |
| 1.22 | Batch file transcription | ✅ Built | `cognitive/perception/audio/handy_adapter.py`, `cognitive/perception/voice_speech/stt/dictation_engine.py` | `HandyAdapter.transcribe_file` / `transcribe_bytes` |
| 1.23 | Speaker diarization (who spoke when) | ❌ Missing | — | `TranscriptionSegment` has speaker field/timestamps only in `voice_speech/core/models.py`; no diarization model |
| 1.24 | Custom vocabulary biasing | ❌ Missing | — | Not exposed in `HandyAdapter` or `DictationEngine` |
| 1.25 | Language auto-detection | ✅ Built | `cognitive/perception/translation/core/detector.py`, `cognitive/perception/audio/handy_adapter.py` | `LocaleDetector` + Whisper detected language field |
| 1.26 | Code-switching within a sentence | ❌ Missing | — | `LocaleDetector` detects dominant script/locale per string |
| 1.27 | Disfluency removal | ⚠️ Partial | `cognitive/perception/voice_speech/stt/dictation_engine.py` | `auto_punctuate` cleans punctuation/formatting; filler-word removal not explicit |
| 1.28 | Reader-ready transcript mode | ⚠️ Partial | `cognitive/perception/voice_speech/stt/dictation_engine.py` | Punctuated transcript output; no paragraph/speaker formatting pipeline |
| 1.29 | Word- and sentence-level timestamps | ✅ Built | `cognitive/perception/audio/handy_adapter.py`, `cognitive/perception/voice_speech/core/models.py` | `TranscriptionSegment(start, end, text)` |
| 1.30 | Voice activity detection | ⚠️ Partial | `cognitive/perception/voice_speech/duplex/voice_session_runner.py` | Turn/barge-in handling present; no Silero/WebRTC VAD detector in `cognitive/perception/audio/` |
| 1.31 | Speaker identification, opt-in only *(new)* | ❌ Missing | — | No speaker embedding/enrollment verification |
| 1.32 | Non-speech audio events *(new)* | ❌ Missing | — | No audio event classifier (music, applause, SFX) |
| 1.33 | Object detection | ✅ Built | `cognitive/perception/vision/vlm_client.py` | `VLMClient.detect_objects` (`live` VLM + heuristic fallback in dev) |
| 1.34 | Face detection and automatic redaction | ❌ Missing | — | No face detection or image redaction pipeline in `cognitive/perception/vision/` |
| 1.35 | Scene classification | ✅ Built | `cognitive/perception/vision/vlm_client.py` | `VLMClient.classify_scene` |
| 1.36 | Image segmentation | ❌ Missing | — | No segmentation mask model |
| 1.37 | Barcode and QR reading | ❌ Missing | — | No barcode/QR decoder |
| 1.38 | Image quality assessment (blur, glare, resolution) | ❌ Missing | — | No blur/glare/resolution scorer |
| 1.39 | Image description (semantic captions) *(new)* | ✅ Built | `cognitive/perception/vision/vlm_client.py` | `VLMClient.analyze_image` |
| 1.40 | Video understanding: events over time, summaries *(new)* | ❌ Missing | — | No temporal video summarizer |
| 1.41 | Visual question answering over images and documents *(new)* | ✅ Built | `cognitive/perception/vision/vlm_client.py` | `VLMClient.analyze_image(..., prompt=...)` |
| 1.42 | Normalized event format for every input | ✅ Built | `cognitive/perception/normalize/provenance.py`, `cognitive/perception/normalize/event_queue.py` | `NormalizedEvent` + `InputNormalizer` |
| 1.43 | Asynchronous processing with results posted back | ✅ Built | `cognitive/perception/normalize/event_queue.py` | Async queue (`asyncio.Queue` / callbacks) |
| 1.44 | Input provenance tagging: source, trust level, time *(new)* | ✅ Built | `cognitive/perception/normalize/provenance.py` | `EventProvenance`, `TrustLevel`, `InputModality`, `utc_now` |
| 1.45 | Modality fallback when the chosen model cannot perceive an input type *(new)* | ⚠️ Partial | `cognitive/perception/vision/paddleocr_adapter.py`, `cognitive/perception/document/unstructured_adapter.py`, `cognitive/perception/vision/vlm_client.py` | Extraction adapters convert images/docs to text, but automatic model-capability-driven modality downgrade router is not centralized in L1 |
| 1.46 | Sign-language recognition, eye-tracking gaze data, and switch or adaptive input devices *(new)* | ⚠️ Stub | `cognitive/perception/accessibility/eye_tracking.py`, `cognitive/perception/accessibility/sign_language.py`, `cognitive/perception/accessibility/switch_driver.py` | Typed driver contracts returning `'not implemented'` for physical hardware/video I/O (pack/driver integration deferred) |
| 1.47 | Current date, time, time zone, locale, device, and what the user is doing right now *(new)* | ✅ Built | `cognitive/perception/situational/context_probe.py`, `control/context/situational/injector.py` | `SituationalContextProbe` collects live OS/tz/locale/time/activity context and injects into L9 context |

---

## L2 Memory (51 features)

> Primary implementation root: `cognitive/memory/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 2.01 | Session context storage | ✅ Built | `cognitive/memory/tiers/working/in_memory.py`, `cognitive/memory/tiers/working/redis_adapter.py`, `cognitive/memory/core/models.py` | `SessionState` + WAL in-memory & Redis Tier 1 |
| 2.02 | Recent message buffer with configurable window | ✅ Built | `cognitive/memory/tiers/working/in_memory.py`, `cognitive/memory/engine.py` | Windowed turn buffering in Tier 1 working memory |
| 2.03 | Token budget tracking per session | ✅ Built | `cognitive/memory/stitches/synthesizer.py`, `cognitive/memory/core/models.py` | `ContextSynthesizer` enforces strict token budgets (`ContextPackage.total_tokens`) |
| 2.04 | Multiple parallel sessions per user | ✅ Built | `cognitive/memory/tiers/working/in_memory.py`, `cognitive/memory/tiers/working/redis_adapter.py` | Keyed by `(user_id, session_id)` |
| 2.05 | Session state persistence and resume | ✅ Built | `cognitive/memory/tiers/working/redis_adapter.py`, `cognitive/memory/tiers/working/in_memory.py` | Redis TTL persistence + in-memory WAL recovery |
| 2.06 | Temporary scratchpad discarded after the task | ✅ Built | `cognitive/memory/tiers/working/in_memory.py`, `cognitive/action/shared_state/scratchpad.py` | Ephemeral Tier 1 session state + task scratchpad |
| 2.07 | Event and interaction storage, per session | ✅ Built | `cognitive/memory/engine.py`, `cognitive/memory/tiers/facts/sqlite_adapter.py`, `cognitive/memory/tiers/facts/postgres_adapter.py` | `MemoryEngine.remember` persists turns and extracted events |
| 2.08 | Searchable full transcripts | ✅ Built | `cognitive/memory/tiers/semantic/qdrant_adapter.py`, `cognitive/memory/tiers/semantic/chroma_adapter.py`, `cognitive/knowledge/search/engines/local_hybrid.py` | Transcript indexing & semantic/keyword retrieval |
| 2.09 | Cross-session recall of similar past cases | ✅ Built | `cognitive/memory/engine.py` | `MemoryEngine.recall` + `get_relevant_lessons` |
| 2.10 | Time-based retrieval ("what happened last week") | ✅ Built | `cognitive/memory/engine.py`, `cognitive/memory/tiers/facts/sqlite_adapter.py`, `cognitive/memory/tiers/graph/age_adapter.py` | Timestamp metadata on facts, turns, and graph edges |
| 2.11 | Entity-based retrieval ("everything about X") | ✅ Built | `cognitive/memory/engine.py`, `cognitive/memory/tiers/graph/age_adapter.py`, `cognitive/memory/tiers/graph/memgraph_adapter.py` | Graph entity traversal (`query_graph`, `multi_hop_query`) |
| 2.12 | Importance scoring | ✅ Built | `cognitive/memory/stitches/consolidation.py`, `cognitive/memory/consolidation/decay_policy.py` | Importance & confidence fields feed decay/retention math |
| 2.13 | Decay, compression and archival policy | ✅ Built | `cognitive/memory/consolidation/decay_policy.py`, `cognitive/memory/stitches/consolidation.py` | `DecayCompressionPolicyEngine` + `ConsolidationEngine.calculate_decay_score` |
| 2.14 | Fact storage | ✅ Built | `cognitive/memory/tiers/facts/sqlite_adapter.py`, `cognitive/memory/tiers/facts/postgres_adapter.py` | `FactItem` CRUD with migrations |
| 2.15 | Knowledge graph of entities and relationships | ✅ Built | `cognitive/memory/tiers/graph/age_adapter.py`, `cognitive/memory/tiers/graph/memgraph_adapter.py`, `cognitive/memory/tiers/graph/_nx_fallback.py` | PostgreSQL+Apache AGE (OSI default), Memgraph opt-in, NetworkX fallback |
| 2.16 | Automatic entity extraction from interactions | ✅ Built | `cognitive/memory/stitches/extractor.py` | Stitch 1 `FactExtractor` |
| 2.17 | Relationship inference | ✅ Built | `cognitive/memory/stitches/extractor.py`, `cognitive/memory/engine.py` | Extracts entities/relations and links via `add_relationship` |
| 2.18 | Fact verification against existing knowledge | ✅ Built | `cognitive/memory/stitches/conflict_resolver.py` | Stitch 3 `ConflictResolver` checks incoming vs existing facts |
| 2.19 | Conflict resolution when new facts contradict old | ✅ Built | `cognitive/memory/stitches/conflict_resolver.py` | Supersedes or deduplicates contradicting `FactItem`s |
| 2.20 | Temporal validity: when a fact was true, and what superseded it *(new)* | ✅ Built | `cognitive/memory/core/models.py`, `cognitive/memory/tiers/facts/sqlite_adapter.py`, `cognitive/memory/stitches/conflict_resolver.py` | Versioning & `superseded_by` / timestamp validity fields |
| 2.21 | Semantic search by meaning | ✅ Built | `cognitive/memory/embeddings/embedder.py`, `cognitive/memory/tiers/semantic/qdrant_adapter.py`, `cognitive/memory/tiers/semantic/chroma_adapter.py` | Dense embedding search across Qdrant/Chroma |
| 2.22 | Learned workflow storage | ⚠️ Partial | `cognitive/memory/lessons/store.py`, `cognitive/learning/demonstration/capability_expander.py` | Procedures/lessons & candidate skills stored, though dedicated L2 parameterized workflow table lives in L7/L8 stores |
| 2.23 | Parameterized workflow templates | ⚠️ Partial | `cognitive/learning/demonstration/capability_expander.py`, `control/orchestration/workflow_builder/` | Workflow templates reside in L7/L8 rather than dedicated L2 store |
| 2.24 | Workflow versioning | ⚠️ Partial | `control/orchestration/workflow_builder/core/models.py`, `cognitive/memory/snapshots/manager.py` | Snapshots capture memory state; workflow-specific versioning lives in L8 |
| 2.25 | Workflow sharing across users and teams | ⚠️ Partial | `surface/federation/review/sharing_gate.py`, `cognitive/action/safety/sharing_pipeline.py` | Cross-user sharing gated via L5/L19 pipelines rather than L2 procedural store |
| 2.26 | Trigger memory: when to activate which workflow | ⚠️ Partial | `control/orchestration/engine/fleet/proactiveInitiation.ts`, `cognitive/memory/lessons/store.py` | Trigger rules sit in L8 `ProactiveInitiationEngine` + L2 lesson tag matching |
| 2.27 | User preferences | ✅ Built | `cognitive/memory/core/models.py`, `cognitive/memory/engine.py` | `FactCategory` user preference facts |
| 2.28 | User history of work and decisions | ✅ Built | `cognitive/memory/engine.py`, `cognitive/memory/tiers/facts/sqlite_adapter.py` | Persistent user history & decisions in Tier 2 |
| 2.29 | User expertise level | ⚠️ Partial | `cognitive/memory/core/models.py`, `cognitive/memory/stitches/extractor.py` | Can be stored as user fact; no dedicated expertise classifier |
| 2.30 | User context: role, organization, permissions | ✅ Built | `cognitive/memory/access_control/openfga_bridge.py`, `cognitive/memory/core/models.py` | Org/user scoping + OpenFGA permission checks (DEF-01) |
| 2.31 | User feedback memory | ✅ Built | `cognitive/memory/lessons/extractor.py`, `cognitive/memory/lessons/store.py` | Stores corrections & feedback as `LessonRecord` |
| 2.32 | User relationship memory | ✅ Built | `cognitive/memory/tiers/graph/age_adapter.py`, `cognitive/memory/engine.py` | Graph relationships & people facts |
| 2.33 | User goal tracking | ✅ Built | `cognitive/memory/core/models.py`, `cognitive/reasoning/src/goals/goalStore.ts` | Goal facts in L2 + dedicated persistent `GoalStore` |
| 2.34 | User style fingerprint (writing, code, design) | ⚠️ Partial | `cognitive/learning/adaptation/scope_applier.py`, `cognitive/memory/core/models.py` | Style preferences stored as facts / L7 adaptations; no dedicated style-vector extractor |
| 2.35 | Separate memory partitions for user, organization, app, agent and session | ✅ Built | `cognitive/memory/core/models.py`, `cognitive/action/sandboxes/memory_partition.py`, `surface/federation/memory/cross_app_sharing.py` | Explicit tenant/user/app/agent/session partition IDs & isolation |
| 2.36 | App state and in-app context memory | ✅ Built | `cognitive/action/sandboxes/memory_partition.py`, `surface/federation/memory/cross_app_sharing.py` | App-scoped partitions & cross-app sharing bridge |
| 2.37 | Organization memory: SOPs, brand voice, policies | ✅ Built | `cognitive/memory/engine.py`, `cognitive/learning/adaptation/scope_applier.py` | Org-scoped facts and adaptation scope (`ORG`) |
| 2.38 | Memory access control: who can see which memory | ✅ Built | `cognitive/memory/access_control/openfga_bridge.py` | OpenFGA bridge (`check_memory_access`, `AccessDeniedError`) — DEF-01 unblocked |
| 2.39 | Background synthesis: working to episodic | ✅ Built | `cognitive/memory/stitches/consolidation.py` | `ConsolidationEngine.consolidate_session` |
| 2.40 | Pattern extraction: episodic to semantic | ✅ Built | `cognitive/memory/stitches/extractor.py`, `cognitive/memory/stitches/consolidation.py` | Extracts semantic `FactItem`s & graph triples from turns |
| 2.41 | Workflow induction from repeated patterns | ✅ Built | `cognitive/learning/demonstration/capability_expander.py`, `cognitive/memory/stitches/consolidation.py` | Repeated pattern induction wired between L2 & L7 |
| 2.42 | User profile update from interactions | ✅ Built | `cognitive/memory/engine.py`, `cognitive/memory/stitches/extractor.py` | Automatic profile/preference updates on `remember` |
| 2.43 | Scheduling: nightly, idle, or on demand | ✅ Built | `cognitive/memory/consolidation/decay_policy.py`, `cognitive/memory/server/app.py` | On-demand `/consolidate` endpoint + policy schedule triggers |
| 2.44 | User can view, edit and delete any stored memory *(new)* | ✅ Built | `cognitive/memory/engine.py` | `get_active_facts`, `update_fact`, `delete_fact`, `delete_archival_memory`, `delete_all_user_memory` |
| 2.45 | "Why was this remembered" source trace *(new)* | ✅ Built | `cognitive/memory/stitches/sources_view.py`, `cognitive/memory/core/models.py` | `SourceProvenance` + `MemorySourcesViewBuilder` + `get_memory_sources` |
| 2.46 | Memory export and portability *(new)* | ✅ Built | `cognitive/memory/portability/manager.py`, `cognitive/memory/portability/translators.py` | `MemoryPortabilityManager.export_memory` + `StandardCITranslator` |
| 2.47 | Memory poisoning defense: untrusted sources cannot write memory *(new)* | ✅ Built | `cognitive/memory/integrity/poisoning_defense.py` | `MemoryPoisoningDefense`, `QuarantineRecord`, `MemoryPoisoningError` |
| 2.48 | Category-based rules for sensitive information *(new)* | ✅ Built | `cognitive/memory/core/models.py`, `cognitive/memory/integrity/poisoning_defense.py`, `control/safety/pii/tier_scrubber.py` | `FactCategory` + sensitivity filtering before storage |
| 2.49 | Lessons-learned memory: store of past failures and corrections *(new)* | ✅ Built | `cognitive/memory/lessons/extractor.py`, `cognitive/memory/lessons/store.py`, `cognitive/memory/lessons/models.py` | `LessonsLearnedExtractor`, `LessonStore`, `MemoryEngine.extract_and_store_lessons` |
| 2.50 | Memory import from another assistant or system *(new)* | ✅ Built | `cognitive/memory/portability/translators.py`, `cognitive/memory/portability/manager.py` | `ChatGPTTranslator`, `ClaudeTranslator`, `StandardCITranslator` |
| 2.51 | Rollback of learned adaptations or memory to an earlier state *(new)* | ✅ Built | `cognitive/memory/snapshots/manager.py`, `cognitive/memory/snapshots/models.py` | `MemorySnapshotManager.create_memory_snapshot` & `rollback_memory` |

---

## L3 Knowledge (46 features)

> Primary implementation root: `cognitive/knowledge/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 3.01 | Document upload (PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB) | ✅ Built | `cognitive/knowledge/rag_api/app/utils/document_loader.py`, `cognitive/knowledge/rag_api/app/routes/document_routes.py`, `cognitive/perception/document/unstructured_adapter.py` | Multi-format document loader + SafePyPDFLoader + Unstructured |
| 3.02 | Web crawling with sitemap traversal | ⚠️ Partial | `cognitive/knowledge/web_search/scraper/crawler.py`, `cognitive/perception/document/crawl4ai_adapter.py` | Polite web crawler & Crawl4AI present; automated XML sitemap discovery/traversal is limited |
| 3.03 | Video transcript ingestion | ❌ Missing | — | No video-transcript ingestion pipeline in `cognitive/knowledge/` |
| 3.04 | Audio and video ingestion | ❌ Missing | — | No audio/video binary ingestion route in `cognitive/knowledge/rag_api/` |
| 3.05 | Database ingestion | ❌ Missing | — | No external SQL/NoSQL database corpus connector in `cognitive/knowledge/` |
| 3.06 | API ingestion | ⚠️ Partial | `cognitive/knowledge/web_search/core/provider.py` | Web/Firecrawl API ingestion present; generic REST-corpus sync scheduler missing |
| 3.07 | Feed ingestion (RSS, news, regulatory updates) | ❌ Missing | — | No RSS/Atom feed poller |
| 3.08 | Email ingestion | ❌ Missing | — | No email-to-knowledge corpus ingestor (`email.ts` is an action connector) |
| 3.09 | Code repository ingestion | ⚠️ Partial | `cognitive/knowledge/rag_api/app/utils/document_loader.py` | Individual code/text files can be uploaded; no Git repo clone/AST indexer |
| 3.10 | Image ingestion with text and description | ⚠️ Partial | `cognitive/perception/vision/vlm_client.py`, `cognitive/perception/vision/paddleocr_adapter.py` | Image OCR/captioning in L1 can feed L3; direct image ingestion route in `rag_api` is minimal |
| 3.11 | Format detection and normalization | ✅ Built | `cognitive/knowledge/rag_api/app/utils/document_loader.py`, `cognitive/knowledge/web_search/scraper/parser.py` | `detect_file_encoding`, `clean_text`, `HTMLMarkdownParser` |
| 3.12 | Chunking strategies (fixed, semantic, sentence, section-aware) | ✅ Built | `cognitive/knowledge/rag/chunker.ts`, `cognitive/knowledge/rag_api/app/utils/document_loader.py`, `cognitive/knowledge/notes/parser.py` | Overlap/page chunking + heading/markdown section parsing |
| 3.13 | Multi-modal embedding generation | ⚠️ Partial | `cognitive/knowledge/rag/embedder.ts`, `cognitive/knowledge/rag_api/app/config.py`, `cognitive/memory/embeddings/embedder.py` | Text embeddings built; native cross-modal image/audio embedding generator not wired |
| 3.14 | Entity and relationship extraction | ✅ Built | `cognitive/knowledge/notes/graph.py`, `cognitive/knowledge/graph/age_adapter.py`, `cognitive/knowledge/graph/falkordb_adapter.py` | Knowledge graph nodes, wiki-links, and AGE/FalkorDB edges |
| 3.15 | Metadata extraction | ✅ Built | `cognitive/knowledge/notes/parser.py`, `cognitive/knowledge/rag_api/app/routes/document_routes.py` | Frontmatter & document metadata extraction |
| 3.16 | Deduplication | ⚠️ Partial | `cognitive/knowledge/search/indexer/corpus_indexer.py`, `cognitive/knowledge/rag/documentIngestion.ts` | Document ID upserts avoid duplicates; near-duplicate MinHash/simhash deduplication absent |
| 3.17 | Source version tracking and re-ingestion | ✅ Built | `cognitive/knowledge/snapshots/manager.py`, `cognitive/knowledge/notes/store.py` | Versioned snapshots & update tracking |
| 3.18 | Semantic index | ✅ Built | `cognitive/knowledge/rag/vectorStore.ts`, `cognitive/knowledge/rag_api/app/services/vector_store/` | PgVector / AtlasMongo / TS in-memory vector store |
| 3.19 | Knowledge graph | ✅ Built | `cognitive/knowledge/graph/age_adapter.py`, `cognitive/knowledge/graph/falkordb_adapter.py`, `cognitive/knowledge/notes/graph.py` | Apache AGE default + FalkorDB opt-in + Note KnowledgeGraph |
| 3.20 | Structured reference data (standards, code sets) | ⚠️ Partial | `cognitive/knowledge/notes/store.py` | Stores markdown/JSON notes; no dedicated schema-validated reference taxonomy table |
| 3.21 | Keyword index | ✅ Built | `cognitive/knowledge/search/engines/local_hybrid.py`, `cognitive/knowledge/rag_api/app/services/hybrid_search.py`, `cognitive/knowledge/search/core/index.py` | SQLite FTS5 + `BM25Okapi` + Meilisearch client |
| 3.22 | Original-document store | ✅ Built | `cognitive/knowledge/notes/store.py`, `cognitive/knowledge/rag_api/app/routes/document_routes.py` | Retains source text & file references |
| 3.23 | Provenance and permission metadata | ✅ Built | `cognitive/knowledge/access_control/openfga_bridge.py`, `cognitive/knowledge/provenance/models.py`, `cognitive/knowledge/rag_api/app/scope.py` | `ScopeFilter` + license provenance + OpenFGA tuples |
| 3.24 | Point-in-time snapshots ("what did the brain know on date T") | ✅ Built | `cognitive/knowledge/snapshots/manager.py`, `cognitive/knowledge/snapshots/models.py` | `KnowledgeSnapshotManager` & `SnapshotDiffResult` |
| 3.25 | Per-domain corpus isolation | ✅ Built | `cognitive/knowledge/notes/store.py`, `cognitive/knowledge/rag_api/app/scope.py`, `cognitive/knowledge/rag_api/app/services/vector_store/factory.py` | Project isolation, `ScopeFilter`, and schema-path separation |
| 3.26 | Semantic search | ✅ Built | `cognitive/knowledge/rag/retriever.ts`, `cognitive/knowledge/search/engines/local_hybrid.py` | Cosine-similarity vector retrieval |
| 3.27 | Keyword search (exact, boolean, pattern) | ✅ Built | `cognitive/knowledge/search/engines/local_hybrid.py`, `cognitive/knowledge/rag_api/app/services/hybrid_search.py` | FTS5 boolean/exact matching + BM25 |
| 3.28 | Hybrid search: semantic, keyword and graph | ✅ Built | `cognitive/knowledge/search/engines/rrf.py`, `cognitive/knowledge/search/engines/local_hybrid.py`, `cognitive/knowledge/rag_api/app/services/hybrid_search.py` | 3-source RRF (`reciprocal_rank_fusion`, `ReciprocalRankFusion`) |
| 3.29 | Multi-hop retrieval across the graph | ✅ Built | `cognitive/knowledge/graph/age_adapter.py`, `cognitive/knowledge/graph/falkordb_adapter.py`, `cognitive/knowledge/notes/graph.py` | Multi-hop traversal over entities & note backlinks |
| 3.30 | Source attribution for every retrieved fact | ✅ Built | `cognitive/knowledge/notebooks/engine.py`, `cognitive/knowledge/core/models.py` | `CitationAnchor` & grounded notebook synthesis |
| 3.31 | Relevance confidence per result | ✅ Built | `cognitive/knowledge/search/core/models.py`, `cognitive/knowledge/abstention/evaluator.py` | Scored `SearchResult` & `EvidenceChunkEvaluation` |
| 3.32 | Re-ranking | ✅ Built | `cognitive/knowledge/rag_api/app/services/hybrid_search.py`, `cognitive/reasoning/src/rerank/router.ts` | `lightweight_rerank` + gateway `/v1/rerank` `RerankEngine` |
| 3.33 | Citation generation | ✅ Built | `cognitive/knowledge/notebooks/engine.py`, `cognitive/knowledge/web_search/verifier/claim_checker.py`, `cognitive/output/citations/formatter.py` | `CitationAnchor`, `WebCitation`, and multi-style formatter |
| 3.34 | Live web augmentation | ✅ Built | `cognitive/knowledge/web_search/core/provider.py`, `cognitive/knowledge/web_search/providers/duckduckgo.py` | Firecrawl, Crawl4AI, and DuckDuckGo providers (Task 2 `live`/`simulated` guarded) |
| 3.35 | Abstain when evidence is insufficient *(new)* | ✅ Built | `cognitive/knowledge/abstention/engine.py`, `cognitive/knowledge/abstention/evaluator.py`, `cognitive/knowledge/abstention/models.py` | `AbstentionEngine` + `GroundingEvidenceEvaluator` + `AbstentionVerdict` |
| 3.36 | Permission-filtered retrieval across private and shared corpora *(new)* | ✅ Built | `cognitive/knowledge/access_control/openfga_bridge.py`, `cognitive/knowledge/search/core/index.py`, `cognitive/knowledge/search/engines/local_hybrid.py` | `filter_results_by_permission` enforced at search time (DEF-02 unblocked) |
| 3.37 | Scheduled source refresh | ❌ Missing | — | No cron/periodic refresh job inside `cognitive/knowledge/` |
| 3.38 | Change detection, re-ingest only what changed | ⚠️ Partial | `cognitive/knowledge/search/core/ingestion.py` | Event-driven ingestion coordinator exists; hash/ETag delta crawler not implemented |
| 3.39 | Auto-discovery of new relevant sources | ❌ Missing | — | No autonomous source-discovery crawler |
| 3.40 | Freshness tracking and stale-knowledge flags | ⚠️ Partial | `cognitive/knowledge/quality/scorer.py` | Recency/freshness signal evaluated at score time; persistent stale-flag sweep missing |
| 3.41 | Corpus scopes per domain or profession | ✅ Built | `cognitive/knowledge/notes/store.py`, `cognitive/knowledge/rag_api/app/scope.py` | Scoped corpora and tenant/project namespaces |
| 3.42 | Knowledge permissions | ✅ Built | `cognitive/knowledge/access_control/openfga_bridge.py` | Fine-grained OpenFGA read/write checks |
| 3.43 | Source quality and authority scoring | ✅ Built | `cognitive/knowledge/quality/scorer.py`, `cognitive/knowledge/quality/models.py` | `SourceQualityAuthorityScorer` (heuristics + LLM-as-Judge) |
| 3.44 | Presenting options when sources disagree | ✅ Built | `cognitive/knowledge/notebooks/engine.py`, `cognitive/reasoning/src/synthesis/claimDecomposer.ts` | Contradiction/disagreement surfaced across claims & sources |
| 3.45 | Licence-aware retrieval: filter or flag results based on usage rights *(new)* | ✅ Built | `cognitive/knowledge/provenance/tagger.py`, `cognitive/knowledge/provenance/models.py` | `LicenseProvenanceTagger` + `LicenseCategory` filtering |
| 3.46 | Record of whether the brain has the right to train on a source *(new)* | ✅ Built | `cognitive/knowledge/provenance/tagger.py`, `cognitive/knowledge/provenance/models.py` | `ProvenanceTagResult` tracks training-rights opt-in/restriction |

---

## L4 Reasoning and Planning (27 cognitive features)

> **Gateway note:** `Layer_04_Reasoning_Planning.md` states: *"Model access is the locked 219-feature gateway spec, carried over unchanged and not re-listed here."* Those gateway mechanics are audited separately in [`docs/GATEWAY_SPEC_AUDIT.md`](GATEWAY_SPEC_AUDIT.md).  
> Primary implementation root: `cognitive/reasoning/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 4.01 | Step-by-step reasoning with visible work | ✅ Built | `cognitive/reasoning/src/security/reasoning.ts`, `cognitive/reasoning/src/agents/hermesAdapter.ts`, `cognitive/reasoning/src/synthesis/prmVerifier.ts` | Preserves/isolates `reasoning_content` & step traces (`ReasoningStep`) |
| 4.02 | Branch exploration: evaluate options, pick the best path | ✅ Built | `cognitive/reasoning/src/synthesis/moaFusion.ts`, `cognitive/reasoning/src/simulation/scenarioSimulator.ts` | Multi-candidate fusion & scenario branch evaluation |
| 4.03 | Plan, act, observe, replan loop | ✅ Built | `cognitive/reasoning/src/agents/hermesAdapter.ts`, `cognitive/action/agent/executor/runner.py`, `control/orchestration/engine/agent/reactLoop.ts` | ReAct / Hermes multi-turn tool loop with replanning |
| 4.04 | Probabilistic reasoning with confidence updates | ✅ Built | `cognitive/reasoning/src/synthesis/prmVerifier.ts`, `cognitive/reasoning/src/synthesis/tieredActivation.ts` | Process Reward Verifier updates per-step & composite confidence |
| 4.05 | Multi-agent debate toward consensus | ✅ Built | `cognitive/reasoning/src/debate/orchestrator.ts`, `cognitive/reasoning/src/debate/models.ts`, `cognitive/reasoning/src/collaboration/controls.ts` | `DebateOrchestrator` + consensus voting |
| 4.06 | Scenario simulation ("what if this fails") | ✅ Built | `cognitive/reasoning/src/simulation/scenarioSimulator.ts`, `cognitive/reasoning/src/simulation/models.ts` | `ScenarioSimulator` with failure-mode injection |
| 4.07 | Adaptive thinking: the model decides how long to think | ✅ Built | `cognitive/reasoning/src/synthesis/tieredActivation.ts`, `cognitive/reasoning/src/security/reasoning.ts` | `TieredActivationGate` dynamically routes light/medium/heavy synthesis |
| 4.08 | Self-correction loop: generate, evaluate, fix, re-evaluate | ✅ Built | `cognitive/reasoning/src/synthesis/prmVerifier.ts`, `cognitive/reasoning/src/synthesis/moaFusion.ts`, `cognitive/reasoning/src/core/engine.ts` | PRM step verification + MoA fusion feedback loop |
| 4.09 | Reflection: review own output before delivering | ✅ Built | `cognitive/reasoning/src/synthesis/claimDecomposer.ts`, `cognitive/reasoning/src/synthesis/prmVerifier.ts` | Decomposes claims & verifies output pre-delivery |
| 4.10 | Task decomposition into sub-goals *(new)* | ✅ Built | `cognitive/reasoning/src/goals/goalStore.ts`, `cognitive/reasoning/src/goals/models.ts`, `control/orchestration/orchestrator/planner/multi_step_planner.py` | `SubGoal` decomposition & DAG layer planning |
| 4.11 | Dependency and ordering analysis *(new)* | ✅ Built | `control/orchestration/orchestrator/planner/multi_step_planner.py`, `cognitive/reasoning/src/goals/goalStore.ts` | Topological dependency/cycle checks & `SubGoal` prerequisites |
| 4.12 | Plan revision when a step fails *(new)* | ⚠️ Partial | `cognitive/reasoning/src/simulation/scenarioSimulator.ts`, `cognitive/reasoning/src/agents/hermesAdapter.ts`, `cognitive/reasoning/src/goals/goalStore.ts` | Supports checkpoints & retry/failure simulation; live mid-flight DAG mutation on step failure is partial |
| 4.13 | Cost, time and resource estimate before execution *(new)* | ✅ Built | `cognitive/reasoning/src/planning/costEstimator.ts`, `cognitive/reasoning/src/planning/models.ts` | `CostEstimator` computes token/cost/latency estimates |
| 4.14 | Plan preview for user approval *(new)* | ✅ Built | `cognitive/reasoning/src/planning/planPreview.ts`, `cognitive/reasoning/src/planning/models.ts` | `PlanPreviewGenerator` renders step/risk preview before execution |
| 4.15 | Goal persistence across sessions for long-horizon work *(new)* | ✅ Built | `cognitive/reasoning/src/goals/goalStore.ts`, `cognitive/reasoning/src/goals/models.ts` | `GoalStore` with persistent checkpoints & resume |
| 4.16 | Code or calculation for exact answers *(new)* | ✅ Built | `cognitive/action/agent/executor/tools/builtin/calculator.py`, `cognitive/action/sandboxes/runner/`, `cognitive/action/tools_mcp/catalog/builtin_tools.py` | Exact AST calculator & sandboxed code execution invoked during reasoning |
| 4.17 | Solver use for math and constraint problems *(new)* | ⚠️ Partial | `cognitive/action/agent/executor/tools/builtin/calculator.py` | Arithmetic calculator present; SMT/MILP constraint solver (e.g., Z3/OR-Tools) not integrated |
| 4.18 | Reasoning over structured data and queries *(new)* | ⚠️ Partial | `cognitive/action/tools_mcp/catalog/builtin_tools.py`, `cognitive/reasoning/src/types/chat.ts` | JSON query tool & structured tool schemas exist; dedicated SQL/dataframe reasoning engine absent in `cognitive/reasoning/` |
| 4.19 | Reasoning across text, image and audio together *(new)* | ⚠️ Partial | `cognitive/reasoning/src/core/engine.ts`, `cognitive/reasoning/src/providers/gemini.ts`, `cognitive/reasoning/src/providers/anthropic.ts`, `cognitive/reasoning/src/realtime/gateway.ts` | Provider translators forward multimodal image/audio payloads; unified cross-modal reasoning fusion module is partial |
| 4.20 | Self-consistency: agreement across multiple attempts *(new)* | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts`, `cognitive/reasoning/src/synthesis/moaFusion.ts` | `CollaborationControls` consensus voting + MoA candidate aggregation |
| 4.21 | Evidence-grounded self-check against retrieved sources *(new)* | ✅ Built | `cognitive/reasoning/src/synthesis/claimDecomposer.ts`, `cognitive/knowledge/abstention/evaluator.py`, `cognitive/knowledge/web_search/verifier/claim_checker.py` | Atomic claim verification against `KnowledgeSource`s |
| 4.22 | Uncertainty expression and abstention *(new)* | ⚠️ Partial | `cognitive/reasoning/src/selfKnowledge/boundaryModule.ts`, `cognitive/knowledge/abstention/engine.py` | Boundary refusal & knowledge abstention built; calibrated token/probability uncertainty narration relies on prompt/evidence scores |
| 4.23 | Ask a clarifying question when a request is ambiguous *(new)* | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts` | Explicit feature-4.23 ambiguity detection & clarification prompts |
| 4.24 | Let the user steer or redirect a run mid-way *(new)* | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts`, `control/orchestration/engine/escalation/humanProtocol.ts` | Mid-run dialogue steering (`humanProtocol.ts` + `controls.ts`) |
| 4.25 | Set how autonomous the brain may be per task *(new)* | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts`, `control/orchestration/engine/escalation/humanProtocol.ts`, `cognitive/action/safety/approval_gate.py` | Suggest / act-with-approval / act-then-report autonomy modes |
| 4.26 | Hand over to a human when the brain reaches limits *(new)* | ✅ Built | `cognitive/reasoning/src/collaboration/controls.ts`, `control/orchestration/engine/escalation/humanProtocol.ts`, `cognitive/action/browser_automation/core/takeover.py` | `HumanEscalationProtocol` + browser `TakeoverManager` |
| 4.27 | Brain knows and states what it can/cannot do, cutoff, active tools *(new)* | ✅ Built | `cognitive/reasoning/src/selfKnowledge/boundaryModule.ts`, `control/context/self_knowledge/injector.py` | `SelfKnowledgeBoundaryModule` (`AgentCapabilityManifest`, cutoff & active tools) |

---

## L5 Action and Tools (47 features)

> Primary implementation root: `cognitive/action/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 5.01 | Standard tool-protocol support (connect external tool servers) | ✅ Built | `cognitive/action/tools_mcp/mcp/client.py`, `cognitive/action/connectors/mcpBridge.ts`, `cognitive/reasoning/src/mcp/gateway.ts` | JSON-RPC 2.0 MCP client & TypeScript MCP bridge |
| 5.02 | Custom tool registration with a schema | ✅ Built | `cognitive/action/tools_mcp/catalog/registry.py`, `cognitive/action/registry/curated_registry.py` | Schema-validated tool registration |
| 5.03 | Permission gating per user and agent | ✅ Built | `cognitive/action/registry/curated_registry.py`, `cognitive/action/safety/approval_gate.py` | RBAC / user+agent tool gating |
| 5.04 | Argument validation before execution | ✅ Built | `cognitive/action/registry/curated_registry.py`, `cognitive/action/tools_mcp/runner/dispatcher.py` | Parameter/JSONSchema validation prior to dispatch |
| 5.05 | Result sanitization after execution | ⚠️ Partial | `cognitive/action/agent/guardrails/filter.py`, `control/safety/pii/tier_scrubber.py` | Guardrail response filtering exists; generic per-tool output sanitizer middleware in `tools_mcp/runner/dispatcher.py` is minimal |
| 5.06 | Per-tool and per-user rate limits | ✅ Built | `cognitive/action/registry/curated_registry.py` | `ToolRateLimitExceededError` enforcement per tool/user |
| 5.07 | Tool call logging for audit | ✅ Built | `cognitive/action/agent/core/event_bus.py`, `control/safety/audit/ledger.py`, `cognitive/action/connectors/pieces/browser.ts` | EventBus audit events & immutable safety audit ledger |
| 5.08 | Curated tool registry: admins add, users request *(new)* | ✅ Built | `cognitive/action/registry/curated_registry.py` | `CuratedToolRegistry` explicitly tagged for Feature 5.08 |
| 5.09 | OAuth and OIDC authenticated access | ✅ Built | `cognitive/action/connectors/nango_adapter.ts`, `cognitive/action/connectors/aci_adapter.ts` | Nango federated OAuth (`live`/`simulated`, prod-guarded) |
| 5.10 | Configurable REST connector | ✅ Built | `cognitive/action/connectors/pieces/http.ts`, `cognitive/action/agent/executor/tools/registry.py` | `httpPiece` + `RestApiTool` |
| 5.11 | Database connector | ❌ Missing | — | No generic SQL/Postgres/MySQL connector piece in `cognitive/action/connectors/pieces/` |
| 5.12 | File-transfer connector | ❌ Missing | — | No SFTP/S3/FTP connector piece (`file_io.py` is local sandbox/file tool) |
| 5.13 | Inbound webhook receiver | ⚠️ Partial | `cognitive/action/connectors/connectorContract.ts`, `cognitive/reasoning/src/telemetry/credits.ts` | Trigger/webhook contracts exist; no general inbound connector webhook HTTP endpoint in `cognitive/action/` |
| 5.14 | Message-queue connector | ⚠️ Partial | `platform_infra/data/messaging/automq_adapter.py`, `cognitive/action/agent/core/event_bus.py` | AutoMQ Kafka adapter sits in `platform_infra`; not exposed as L5 `ConnectorPiece` |
| 5.15 | Connectors on by default but idle until needed *(new)* | ✅ Built | `cognitive/action/tools_mcp/catalog/registry.py`, `cognitive/action/tools_mcp/auth/on_demand_auth.py` | Explicit idle-until-needed catalog state |
| 5.16 | Credentials requested only at first use *(new)* | ✅ Built | `cognitive/action/tools_mcp/auth/on_demand_auth.py`, `cognitive/action/tools_mcp/runner/dispatcher.py` | `OnDemandAuthBridge` queues credential prompt only when invoked |
| 5.17 | Active only after key/OAuth + successful ping test *(new)* | ⚠️ Partial | `cognitive/action/connectors/nango_adapter.ts`, `cognitive/action/tools_mcp/auth/on_demand_auth.py` | Health/connection check helpers present; formal ping-before-activation FSM across all connectors is partial |
| 5.18 | No session-cookie authentication *(new)* | ⚠️ Partial | `control/safety/auth/oauthStrategies.ts`, `cognitive/action/connectors/nango_adapter.ts` | Connectors use API key / OAuth tokens rather than scraped cookies; explicit static policy validator enforcing 5.18 absent |
| 5.19 | Connection health checks and re-authorization prompts *(new)* | ✅ Built | `cognitive/action/connectors/nango_adapter.ts`, `cognitive/action/tools_mcp/auth/on_demand_auth.py` | `OnDemandAuthBridge` + Nango connection status checks |
| 5.20 | Request flow: users ask for a connector, admins decide *(new)* | ⚠️ Partial | `cognitive/action/registry/curated_registry.py`, `cognitive/action/safety/sharing_pipeline.py` | Pattern built for curated tools & promotions; connector-specific admin request queue is partial |
| 5.21 | Modify external systems | ✅ Built | `cognitive/action/connectors/pieces/slack.ts`, `email.ts`, `calendar.ts`, `openclaw.ts`, `surface/federation/pm/huly_adapter.py` | Concrete write-back connectors (Huly prod-guarded) |
| 5.22 | Approval gates by risk: low runs, medium confirms, high confirms with reason | ✅ Built | `cognitive/action/safety/risk_classifier.py`, `cognitive/action/safety/approval_gate.py`, `cognitive/action/safety/models.py` | Tiered `RiskLevel` classification & `ApprovalGate` |
| 5.23 | Rollback of the last action where possible | ✅ Built | `cognitive/action/safety/compensation.py` | `CompensationManager` & `CompensationHook` undo stack |
| 5.24 | Dry run: simulate without executing | ✅ Built | `cognitive/action/safety/blast_radius.py` | `BlastRadiusSimulator` dry-run impact simulation |
| 5.25 | Batching writes into one transaction | ⚠️ Partial | `cognitive/action/shared_state/lock_manager.py` | Distributed lock coordination exists; atomic multi-connector transaction coordinator is absent |
| 5.26 | Idempotency: no duplicate actions on retry *(new)* | ⚠️ Partial | `cognitive/action/shared_state/lock_manager.py` | Lock leases prevent concurrent duplicate execution; dedicated idempotency-key deduplication store absent |
| 5.27 | Action preview showing the exact effect *(new)* | ✅ Built | `cognitive/action/safety/action_preview.py` | `ActionPreviewRenderer` (Feature 5.27) |
| 5.28 | Computer use: screen, mouse, keyboard | ✅ Built | `cognitive/action/connectors/pieces/openclaw.ts`, `cognitive/reasoning/src/agents/openclawAdapter.ts` | `OpenClawOSAction` computer-use bridge |
| 5.29 | Local file and machine access | ✅ Built | `cognitive/action/agent/executor/tools/builtin/file_io.py`, `cognitive/action/sandboxes/runner/local_process_runner.py`, `cognitive/action/remote_access/` | Governed file I/O, local runner, and remote device pairing |
| 5.30 | Browser automation | ✅ Built | `cognitive/action/browser_automation/core/agent.py`, `cognitive/action/browser_automation/core/takeover.py`, `cognitive/action/connectors/pieces/browser.ts` | Playwright adapter, sensitive-field/CAPTCHA takeover, confirmation rules |
| 5.31 | Code execution sandbox | ✅ Built | `cognitive/action/sandboxes/runner/docker_runner.py`, `cognitive/action/agent/sandbox/e2b_adapter.py`, `cognitive/action/sandboxes/core/engines.py` | E2B (Task 2 prod-guarded) & Docker sandboxes |
| 5.32 | Deep research: autonomous multi-step, cited report | ✅ Built | `cognitive/action/agent/builder/templates/researcher.py`, `cognitive/action/agent/executor/runner.py`, `cognitive/knowledge/notebooks/engine.py` | `ResearcherAgentBlueprint` + autonomous runner + cited synthesis |
| 5.33 | Sandbox resource and network limits *(new)* | ✅ Built | `cognitive/action/sandboxes/governor/security_governor.py`, `cognitive/action/sandboxes/core/models.py` | `SecurityGovernor` & `ResourceLimits` (tested in `test_feature_533_limits.py`) |
| 5.34 | Agent creation: name, persona, capabilities, permissions | ✅ Built | `cognitive/action/agent/core/manifest.py`, `cognitive/action/agent_builder/core/models.py`, `cognitive/action/agent_builder/compiler/describe_to_agent.py` | `AgentManifest` & `DescribeToAgentCompiler` |
| 5.35 | Persona system (tone, style) | ✅ Built | `cognitive/action/agent_builder/core/models.py`, `cognitive/action/agent/core/manifest.py` | `AgentPersona` binding |
| 5.36 | Capability scoping | ✅ Built | `cognitive/action/agent/core/manifest.py`, `cognitive/action/agent_builder/compiler/tool_matcher.py` | Explicit tool & subagent capability manifest |
| 5.37 | Permission scoping | ✅ Built | `cognitive/action/agent_builder/binding/rules_binder.py`, `control/identity/agent/agent_identity.py` | `RulesBinder` & scoped agent identity |
| 5.38 | Per-agent memory separate from user memory | ✅ Built | `cognitive/action/sandboxes/memory_partition.py` | `AgentMemoryPartition` & `MemoryPartitionManager` (Feature 5.38) |
| 5.39 | Lifecycle: create, configure, pause, delete | ✅ Built | `cognitive/action/agent/server/api.py`, `cognitive/action/agent_builder/runtime/agent_instantiator.py`, `control/orchestration/engine/fleet/paperclipAdapter.ts` | Agent creation/config/pause/delete lifecycle |
| 5.40 | Sharing: private, team or organization | ✅ Built | `cognitive/action/safety/sharing_pipeline.py` | `SharingScope` & promotion workflow |
| 5.41 | Curated agent templates | ✅ Built | `cognitive/action/agent/builder/templates/coder.py`, `researcher.py`, `support.py` | Pre-packaged blueprints |
| 5.42 | Activity log and analytics | ✅ Built | `cognitive/action/agent/core/event_bus.py`, `cognitive/action/agent/server/api.py`, `control/orchestration/internal_agents/storage/sqlite_agent_log.py` | Agent telemetry & append-only SQLite activity logs |
| 5.43 | Agent-to-agent handoff | ✅ Built | `cognitive/action/agent/executor/subagent_manager.py`, `cognitive/reasoning/src/agents/a2a.ts`, `control/orchestration/engine/fleet/collaborationBridge.ts` | `SubagentManager` + A2A router |
| 5.44 | Shared scratch space for parallel agents on same task *(new)* | ✅ Built | `cognitive/action/shared_state/scratchpad.py` | `SharedScratchpad` with mutation audit (Feature 5.44) |
| 5.45 | Locking / conflict checks on external writes *(new)* | ✅ Built | `cognitive/action/shared_state/lock_manager.py` | `DistributedLockManager` lease locking (Feature 5.45) |
| 5.46 | Payments/purchases on user's behalf with spend limits, approval & receipts *(new)* | ✅ Built | `cognitive/action/safety/financial_authority.py`, `control/identity/financial/authority_bridge.py` | `FinancialAuthorityGuard` (`test_financial_authority.py`) |
| 5.47 | Agents & workflows pass review before private -> team/org *(new)* | ✅ Built | `cognitive/action/safety/sharing_pipeline.py`, `surface/federation/review/sharing_gate.py` | `ReviewSharingPipeline` (Feature 5.47) |

---

## L6 Output (40 features)

> Primary implementation root: `cognitive/output/` (plus `cognitive/reasoning/src/{images,audio,videos}/`)

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 6.01 | Plain text | ✅ Built | `cognitive/output/format_negotiator.py`, `cognitive/output/editor/tiptap_adapter.ts` | Negotiates & renders plain text |
| 6.02 | Markdown | ✅ Built | `cognitive/output/documents/template_engine.py`, `cognitive/output/format_negotiator.py` | Markdown report & TOC assembly |
| 6.03 | Rich text and HTML | ✅ Built | `cognitive/output/editor/tiptap_adapter.ts`, `cognitive/output/format_negotiator.py` | TipTap headless editor + HTML negotiation |
| 6.04 | Code as text output | ✅ Built | `cognitive/output/format_negotiator.py`, `cognitive/output/editor/tiptap_adapter.ts` | Code blocks & structured formatting |
| 6.05 | Math and LaTeX | ⚠️ Partial | `cognitive/output/editor/tiptap_adapter.ts`, `cognitive/output/format_negotiator.py` | Text/Markdown preserves `$` LaTeX; no server-side KaTeX/MathJax AST validator |
| 6.06 | Multi-language output with translation | ✅ Built | `cognitive/perception/translation/core/middleware.py`, `cognitive/perception/translation/core/engine.py` | `AutoTranslateMiddleware` handles bidirectional translated output |
| 6.07 | Text to image | ⚠️ Partial | `cognitive/reasoning/src/images/generate.ts`, `cognitive/output/media_gen/engines/image_engine.py` | Gateway `/v1/images/generations` proxies real provider; `media_gen/image_engine.py` emits synthetic PNG bytes for offline tests |
| 6.08 | Image to image | ❌ Missing | — | Not implemented in `ImageGenerationEngine` or `ImageRouter` |
| 6.09 | Editing and inpainting | ⚠️ Partial | `cognitive/reasoning/src/images/generate.ts` | `/v1/images/edits` proxy route exists in `server.ts`; local/media_gen mask inpainting not implemented |
| 6.10 | Outpainting | ❌ Missing | — | No outpainting support |
| 6.11 | Variations | ⚠️ Partial | `cognitive/output/media_gen/engines/image_engine.py` | Docstring mentions variations, `generate()` supports single seed/prompt signature only |
| 6.12 | Style transfer | ❌ Missing | — | No style-transfer image pipeline |
| 6.13 | Upscaling | ❌ Missing | — | No super-resolution / image upscaler |
| 6.14 | Editable vector graphics | ✅ Built | `cognitive/output/canvas/tldraw_adapter.ts`, `cognitive/output/diagrams/mermaid_adapter.ts` | Tldraw scene shapes & Mermaid diagrams |
| 6.15 | Text to speech | ⚠️ Partial | `cognitive/reasoning/src/audio/speech.ts`, `cognitive/output/voice_speech/tts/synthesis_engine.py`, `cognitive/output/media_gen/engines/audio_engine.py` | Gateway proxies OpenAI TTS; local `SpeechSynthesizer` / `AudioGenerationEngine` produce synthetic/stub waveforms without live model weights |
| 6.16 | Voice cloning, with consent | ❌ Missing | — | No voice-cloning engine or voiceprint consent workflow |
| 6.17 | Multiple voices for multiple speakers | ❌ Missing | — | Single voice parameter only in `SpeechRequest` |
| 6.18 | Real-time speech to speech | ⚠️ Partial | `cognitive/output/voice_speech/duplex/voice_session_runner.py`, `cognitive/reasoning/src/realtime/gateway.ts` | Duplex session loop & WebSocket gateway scaffold; relies on upstream Realtime API |
| 6.19 | Audio overview of sources (two-host discussion) | ❌ Missing | — | No two-host podcast/overview script+TTS pipeline |
| 6.20 | Voice style control: emotion, pace, emphasis, accent | ⚠️ Partial | `cognitive/reasoning/src/audio/speech.ts`, `cognitive/output/voice_speech/core/models.py` | `speed` parameter present; emotion/emphasis/accent SSML controls missing |
| 6.21 | Schema-enforced JSON | ✅ Built | `cognitive/reasoning/src/types/chat.ts`, `cognitive/output/format_negotiator.py` | Zod schema enforcement & JSON target negotiation |
| 6.22 | Tables and spreadsheets | ✅ Built | `cognitive/output/generative_ui/copilotkit_adapter.ts`, `control/orchestration/nodes/core/ToMarkdownTableNode.ts` | Structured `TableColumn` widget & Markdown tables |
| 6.23 | Conformance to external API schemas | ✅ Built | `cognitive/reasoning/src/types/chat.ts`, `cognitive/output/format_negotiator.py` | Typed schema validation & payload adaptation |
| 6.24 | Filling any structured form | ✅ Built | `cognitive/output/generative_ui/copilotkit_adapter.ts` | `FormField` / `FormConfig` generative UI bindings |
| 6.25 | Multi-section reports with table of contents and citations | ✅ Built | `cognitive/output/documents/template_engine.py` | `DocumentTemplateEngine` (`REPORT`, `EXECUTIVE_BRIEF`, `TECHNICAL_SPEC`) |
| 6.26 | Slide presentations | ⚠️ Partial | `cognitive/output/documents/template_engine.py` | `DocumentType.SLIDES` produces structured Markdown slides; no `.pptx` binary exporter |
| 6.27 | Documents with embedded media, charts and tables | ✅ Built | `cognitive/output/documents/template_engine.py`, `cognitive/output/diagrams/mermaid_adapter.ts` | `ReportSection.embedded_media` + Mermaid diagrams |
| 6.28 | Template-based generation | ✅ Built | `cognitive/output/documents/template_engine.py`, `cognitive/output/media_gen/core/templates.py` | Document & media prompt template engines |
| 6.29 | Working app or dashboard from a prompt | ✅ Built | `cognitive/output/generative_ui/copilotkit_adapter.ts`, `cognitive/action/agent_builder/composer/app_composer.py`, `layout_engine.py` | `CopilotKitAdapter` + `AppComposer` / `LayoutEngine` |
| 6.30 | Quizzes and games from sources | ❌ Missing | — | No interactive quiz/game generator |
| 6.31 | Provenance marking of generated media: watermark and metadata *(new)* | ✅ Built | `cognitive/output/integrity/watermarker.py` | `CryptographicWatermarker` & `ProvenanceVerificationResult` |
| 6.32 | "AI-generated" labeling *(new)* | ✅ Built | `cognitive/output/integrity/watermarker.py` | `WatermarkPayload` embeds `"AI-generated"` provenance disclosure |
| 6.33 | Citation formatting per style *(new)* | ✅ Built | `cognitive/output/citations/formatter.py` | `CitationFormatter` supporting multiple citation styles (`CitationStyle`) |
| 6.34 | Accessible output: alt text, captions, readable structure *(new)* | ✅ Built | `cognitive/output/accessibility/renderer.py` | `AccessibleOutputRenderer`, `AccessibleImageOutput`, `CaptionCue` |
| 6.35 | Output format negotiation for the target surface *(new)* | ✅ Built | `cognitive/output/format_negotiator.py` | `OutputFormatNegotiator` & `TargetSurface` |
| 6.36 | Streaming of partial output *(new)* | ✅ Built | `cognitive/reasoning/src/core/stream.ts`, `cognitive/reasoning/src/core/stream-failover.ts` | SSE `StreamNormalizer` & failover stream delivery |
| 6.37 | Edit history, diffs, undo and restore for documents/artifacts *(new)* | ✅ Built | `cognitive/output/integrity/claim_diff_patcher.py`, `cognitive/output/editor/tiptap_adapter.ts` | `ClaimDiffPatcher` surgical claim patching + editor document state |
| 6.38 | Real-time co-editing of generated content with conflict resolution *(new)* | ✅ Built | `cognitive/output/collaboration/conflict_resolver.py` | `ConflictResolver` with OT/text operations (`OpType`, `TextOperation`) |
| 6.39 | No reproduction of protected material in output *(new)* | ⚠️ Partial | `control/safety/rights/content_rights.py` | Implemented in L10 (`ContentRightsEnforcer`, 8-word n-gram match); not yet invoked directly by `cognitive/output/` pipeline |
| 6.40 | Attribution rules for generated content drawing on sources *(new)* | ⚠️ Partial | `control/safety/rights/content_rights.py`, `cognitive/output/citations/formatter.py` | Attribution enforcement lives in L10 `ContentRightsEnforcer`; L6 formats citations |

---

## L7 Learning and Adaptation (29 features)

> Primary implementation root: `cognitive/learning/`

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 7.01 | Explicit thumbs up and down | ✅ Built | `cognitive/learning/rl/routing_weight_adjuster.py`, `control/evaluation/accuracy/feedback_pillar.py` | Explicit thumbs-up/down `FeedbackEvent` updates weights |
| 7.02 | Edit-based feedback: learn from the user's changes | ❌ Missing | — | No diff-based edit-feedback collector or learner in `cognitive/learning/` |
| 7.03 | Rejection feedback | ✅ Built | `cognitive/learning/rl/routing_weight_adjuster.py`, `cognitive/memory/lessons/extractor.py` | Negative feedback shifts RL routing weights & extracts lessons |
| 7.04 | Acceptance feedback | ✅ Built | `cognitive/learning/rl/routing_weight_adjuster.py`, `cognitive/learning/synthetic/data_generator.py` | Accepted traces boost weights & seed training examples |
| 7.05 | Ratings | ✅ Built | `cognitive/learning/rl/routing_weight_adjuster.py`, `control/evaluation/online/satisfaction.py` | Numeric rating feedback incorporated into scoring |
| 7.06 | Implicit signals: reading time, copy, scroll | ❌ Missing | — | No implicit UI dwell/copy/scroll telemetry collector |
| 7.07 | Surveys and NPS | ❌ Missing | — | No NPS/survey capture module |
| 7.08 | Error report submission | ⚠️ Partial | `cognitive/memory/lessons/extractor.py`, `cognitive/learning/recommender/` | Error recovery feeds lessons; no user bug-report submission intake in L7 |
| 7.09 | Response style preference | ✅ Built | `cognitive/learning/adaptation/scope_applier.py`, `cognitive/learning/langmem/langmem_adapter.py` | Scoped preference adaptations (`USER`, `APP`, etc.) |
| 7.10 | Model preference per user | ✅ Built | `cognitive/learning/recommender/engine/recommender_service.py`, `cognitive/learning/rl/routing_weight_adjuster.py` | Empirical scorer & user-weighted model selection |
| 7.11 | Prompt formulation preference | ⚠️ Partial | `cognitive/learning/agenta/agenta_adapter.py` | Variant management exists; automated per-user prompt rewriting preference is partial |
| 7.12 | Routing weight adjustment from feedback | ✅ Built | `cognitive/learning/rl/routing_weight_adjuster.py` | `RoutingWeightAdjuster` (Feature 7.12) |
| 7.13 | Per-user style adaptation | ✅ Built | `cognitive/learning/adaptation/scope_applier.py` | `AdaptationScope.USER` enforcement |
| 7.14 | Per-organization convention adaptation | ✅ Built | `cognitive/learning/adaptation/scope_applier.py` | `AdaptationScope.ORG` enforcement |
| 7.15 | Adaptation applied at user, org, profession and app scope | ✅ Built | `cognitive/learning/adaptation/scope_applier.py` | `AdaptationScopeApplier` (`USER` -> `APP` -> `PROFESSION` -> `ORG` -> `GLOBAL`) |
| 7.16 | Training data collection (good and bad examples) | ✅ Built | `cognitive/learning/synthetic/data_generator.py`, `cognitive/learning/consent/lineage_tracker.py` | `SyntheticDatasetGenerator` exports ChatML/OpenAI/Gemini JSONL |
| 7.17 | Automated data curation and deduplication | ❌ Missing | — | No automated dedup/quality filter over JSONL training datasets |
| 7.18 | Parameter-efficient tuning | ❌ Missing | — | No LoRA/QLoRA/PEFT training runner |
| 7.19 | Full tuning | ❌ Missing | — | No full fine-tuning trainer/job launcher (metadata/API stub in L4 `files/manager.ts`) |
| 7.20 | Preference-based optimization | ⚠️ Partial | `cognitive/learning/rl/routing_weight_adjuster.py`, `cognitive/learning/agenta/agenta_adapter.py` | Online bandit/RL weight shifting built; DPO/RLHF weight optimizer absent |
| 7.21 | Consent and opt-out for use of data in training *(new)* | ✅ Built | `cognitive/learning/consent/consent_manager.py` | `TrainingConsentManager` wired with L10 c15t |
| 7.22 | Training-data lineage *(new)* | ✅ Built | `cognitive/learning/consent/lineage_tracker.py` | `TrainingLineageTracker` + `TrainingDataProvenance` |
| 7.23 | Workflow pattern detection from repeated behavior | ✅ Built | `cognitive/learning/demonstration/capability_expander.py` | Detects >=3 repeated interaction sequences |
| 7.24 | Automation suggestion to the user | ⚠️ Partial | `cognitive/learning/demonstration/capability_expander.py`, `surface/interaction/proactive/nudge_engine.py` | Proposes `CandidateSkill`s for approval; conversational suggestion UX sits in L18 |
| 7.25 | Capability expansion from user demonstration | ✅ Built | `cognitive/learning/demonstration/capability_expander.py` | `CapabilityExpander` synthesizes `CandidateSkill` from `UserAction` traces |
| 7.26 | Human review before an acquired skill activates *(new)* | ✅ Built | `cognitive/learning/demonstration/capability_expander.py` | `SkillStatus` approval gate before skill activation |
| 7.27 | Store of past failures and corrections, applied to avoid repeating *(new)* | ✅ Built | `cognitive/memory/lessons/store.py`, `cognitive/memory/lessons/extractor.py`, `cognitive/learning/cognee/cognee_adapter.py` | Cross-layer L2/L7 lessons-learned engine |
| 7.28 | Generate training and evaluation data synthetically *(new)* | ✅ Built | `cognitive/learning/synthetic/data_generator.py` | `SyntheticDatasetGenerator` |
| 7.29 | Human labeling workflow for training and eval data *(new)* | ✅ Built | `cognitive/learning/synthetic/labeling_workflow.py` | `LabelingWorkflowQueue` (`ReviewStatus`, `ReviewItem`) |

---

## L8 Orchestration (50 features)

> Primary implementation root: `control/orchestration/` (plus `cognitive/action/shared_state/` & `cognitive/reasoning/`)

| Feature ID | Spec Description | Status | File(s) | Notes |
|---|---|---|---|---|
| 8.01 | Task type detection | ✅ Built | `control/orchestration/engine/routing/taskClassifier.ts`, `cognitive/reasoning/routing/taskClassifier.ts` | `classifyTask` |
| 8.02 | Domain detection | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `control/orchestration/engine/routing/taskClassifier.ts` | Domain-aware specialist policy selection |
| 8.03 | Complexity assessment | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts` | Feature 8.09/8.03 dynamic complexity scoring |
| 8.04 | Urgency detection | ⚠️ Partial | `control/orchestration/resource_optimizer/models.py`, `control/orchestration/engine/routing/cognitivePolicy.ts` | Priority/SLA inputs accepted on descriptors; NLP urgency classifier not standalone |
| 8.05 | Route to the right layer or capability | ✅ Built | `control/orchestration/engine/index.ts`, `control/orchestration/engine/routing/router.ts` | `ModelEngine` + `OmniRouter` 4-path priority router |
| 8.06 | Route to the right specialized brain or pack | ⚠️ Partial | `control/orchestration/engine/routing/cognitivePolicy.ts`, `surface/federation/brain/brain_factory.py` | Domain specialist selection built; full pack routing awaits domain packs (`Appendix_A_Packs.md`) |
| 8.07 | Route to the right app | ⚠️ Partial | `surface/interaction/universal/surface_adapter.py`, `control/orchestration/engine/routing/router.ts` | Surface/app routing hooks exist across L8/L18 |
| 8.08 | Cross-app task orchestration | ✅ Built | `control/orchestration/workflow_builder/runtime/orchestrator_bridge.py`, `control/orchestration/orchestrator/engine/dag_runner.py` | Multi-step DAG workflows span connectors & apps |
| 8.09 | Cost-optimized routing | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `cognitive/reasoning/routing/selector.ts` | Cost-quality Pareto optimization (`RoutingObjective`) |
| 8.10 | Latency-optimized routing | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `control/orchestration/go-routing/adaptive.go` | Latency SLA filtering & adaptive weights |
| 8.11 | Quality-optimized routing | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `cognitive/learning/recommender/engine/recommender_service.py` | Quality objective & empirical recommender |
| 8.12 | Per-task model selection | ✅ Built | `control/orchestration/engine/routing/selector.ts`, `control/orchestration/engine/routing/cognitivePolicy.ts` | `selectModel` & policy evaluation |
| 8.13 | User can always pick a model from dropdown, even when auto-selection on *(new)* | ✅ Built | `control/orchestration/engine/types.ts`, `control/orchestration/engine/index.ts`, `cognitive/learning/recommender/engine/recommender_service.py` | Explicit model override bypasses Auto selection |
| 8.14 | Tenant model policy | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `control/orchestration/engine/governance/virtualKeyManager.ts` | Declarative `PolicyRule`s + virtual-key model whitelists |
| 8.15 | Second opinion on low accuracy if better model free & no extra cost *(new)* | ✅ Built | `control/orchestration/engine/routing/cognitivePolicy.ts`, `cognitive/learning/recommender/engine/second_opinion.py` | `maybeTriggerSecondOpinion` (DEF-03 unblocked; `tests/secondOpinion.test.ts`) |
| 8.16 | Single-agent loop | ✅ Built | `control/orchestration/engine/agent/reactLoop.ts`, `cognitive/action/agent/executor/runner.py` | `runReActLoop` & `AgentRunner` |
| 8.17 | Multi-step execution | ✅ Built | `control/orchestration/orchestrator/planner/multi_step_planner.py`, `control/orchestration/orchestrator/engine/dag_runner.py` | `MultiStepPlanner` + `ParallelDAGRunner` |
| 8.18 | Parallel execution | ✅ Built | `control/orchestration/orchestrator/engine/dag_runner.py`, `control/orchestration/engine/fleet/paperclipAdapter.ts` | Concurrent fan-out/fan-in layers + Paperclip fleet |
| 8.19 | Sequential handoff between agents | ✅ Built | `control/orchestration/engine/fleet/collaborationBridge.ts`, `control/orchestration/workflow_builder/compiler/describe_to_workflow.py` | DAG edges & delegation handoffs |
| 8.20 | Sub-agent spawning | ✅ Built | `cognitive/action/agent/executor/subagent_manager.py`, `control/orchestration/engine/fleet/collaborationBridge.ts` | `SubagentManager` & recursion-bounded `CollaborationBridge` |
| 8.21 | Agent state management | ✅ Built | `control/orchestration/engine/agent/agentRegistry.ts`, `control/orchestration/engine/fleet/paperclipAdapter.ts` | `AgentRegistry` & `PaperclipGovernanceAdapter` |
| 8.22 | Session persistence and resume | ✅ Built | `control/orchestration/orchestrator/storage/sqlite_plan_store.py` | `SQLitePlanStore` checkpointing & resumption |
| 8.23 | Cancellation | ✅ Built | `control/orchestration/orchestrator/engine/cancellation.py`, `control/orchestration/engine/agent/killSwitch.ts` | `CancellationToken` + `AgentKillSwitchTS` |
| 8.24 | Timeouts | ✅ Built | `control/orchestration/orchestrator/engine/dag_runner.py`, `control/orchestration/resource_optimizer/core/optimizer.py` | Node execution timeouts & lease reaping |
| 8.25 | Retry with backoff | ✅ Built | `control/orchestration/go-resilience/circuitbreaker.go`, `fallback.go`, `cognitive/reasoning/src/resilience/cooldown.ts` | Circuit breaker, exponential backoff & fallback |
| 8.26 | Cost tracking per run | ✅ Built | `control/orchestration/engine/governance/usageStore.ts`, `budgetTracker.ts`, `orchestrator/guard/budget_guard.py` | Real-time run cost & budget enforcement |
| 8.27 | Conditional branching | ✅ Built | `control/orchestration/nodes/core/IfNode.ts`, `IfElseNode.ts`, `MatchNode.ts` | Graph conditional branching nodes |
| 8.28 | Loops and iteration | ✅ Built | `control/orchestration/nodes/core/LoopControllerNode.ts`, `LoopUntilNode.ts`, `ChatLoopNode.ts` | Bounded loop control nodes |
| 8.29 | Workflow versioning and rollback | ⚠️ Partial | `control/orchestration/workflow_builder/core/models.py`, `orchestrator/storage/sqlite_plan_store.py` | Models support versions; automated workflow-definition rollback manager is partial |
| 8.30 | Workflow sharing | ⚠️ Partial | `control/orchestration/engine/escalation/humanProtocol.ts`, `cognitive/action/safety/sharing_pipeline.py` | Promotion pipeline handles review/sharing; standalone workflow marketplace share API absent |
| 8.31 | Long-running durable workflows (hours–days; **deferred past v1**) | 📦 Deferred (scaffold built) | `control/orchestration/workflow_builder/runtime/temporal_adapter.py`, `control/orchestration/engine/temporalBridge.ts` | Marked deferred past v1 in spec (`Appendix_B_Mapping.md`), but `TemporalWorkflowAdapter` & `TemporalBridge` scaffold exists |
| 8.32 | Event triggers | ✅ Built | `control/orchestration/engine/fleet/proactiveInitiation.ts`, `nodes/core/WaitForEventNode.ts`, `RaiseEventNode.ts` | `ProactiveInitiationEngine.evaluateEvent` & event nodes |
| 8.33 | Schedule triggers | ✅ Built | `control/orchestration/nodes/core/CronNode.ts`, `internal_agents/scheduler/background_runner.py`, `proactiveInitiation.ts` | `CronNode` + `TriggerType = 'schedule'` + `BackgroundAgentScheduler` |
| 8.34 | Webhook triggers | ⚠️ Partial | `cognitive/action/connectors/connectorContract.ts`, `control/orchestration/engine/fleet/proactiveInitiation.ts` | Trigger event bus supports webhook events; dedicated HTTP ingress webhook router for workflows is partial |
| 8.35 | Background execution while user is away | ✅ Built | `control/orchestration/internal_agents/scheduler/background_runner.py`, `workflow_builder/runtime/temporal_adapter.py` | `BackgroundAgentScheduler` + visible SQLite log |
| 8.36 | Proactive initiation within user-set rules | ✅ Built | `control/orchestration/engine/fleet/proactiveInitiation.ts` | `ProactiveInitiationEngine` (`InitiationRule` guards) |
| 8.37 | Real-time priority | ✅ Built | `control/orchestration/resource_optimizer/core/optimizer.py`, `models.py` | `ResourceOptimizer` priority lease scheduling |
| 8.38 | Background priority | ✅ Built | `control/orchestration/resource_optimizer/core/optimizer.py`, `internal_agents/scheduler/background_runner.py` | Priority tiering & CPU/RAM throttling |
| 8.39 | Scheduled priority | ⚠️ Partial | `control/orchestration/resource_optimizer/core/optimizer.py`, `nodes/core/CronNode.ts` | Priority queues can label scheduled tasks; dedicated cron-tier preemption queue is partial |
| 8.40 | Emergency priority that preempts everything | ⚠️ Partial | `control/orchestration/engine/agent/killSwitch.ts`, `resource_optimizer/core/optimizer.py` | Kill switch & escalation urgency exist; active preemption of running GPU/LLM tasks in `ResourceOptimizer` is partial |
| 8.41 | Token budgets per tenant and user | ✅ Built | `control/orchestration/engine/governance/budgetTracker.ts`, `rateLimiter.ts`, `virtualKeyManager.ts` | Tenant/user token & spend limits |
| 8.42 | Downgrade to cheaper model when quality bar allows | ✅ Built | `control/orchestration/engine/governance/budgetTracker.ts`, `engine/routing/cognitivePolicy.ts` | `DegradationAction` & cost-quality Pareto routing |
| 8.43 | Batch processing of non-urgent requests | ✅ Built | `cognitive/reasoning/src/batches/manager.ts` | Gateway `/v1/batches` async batch manager (no L8 automatic non-urgent queue batcher yet) |
| 8.44 | Semantic cache | ✅ Built | `control/orchestration/engine/caching/semanticCacheBridge.ts`, `cognitive/reasoning/src/caching/semantic.ts` | `SemanticCacheBridge` + `SemanticCache` (Feature 8.44) |
| 8.45 | Embedding cache | ⚠️ Partial | `cognitive/perception/translation/core/cache.py`, `cognitive/reasoning/src/caching/cache.ts` | Exact response/translation caches built; standalone embedding-vector cache keyer is partial |
| 8.46 | Output cache | ✅ Built | `control/orchestration/go-cache/cache.go`, `cognitive/reasoning/src/caching/cache.ts` | `ResponseCache` + Go LRU/cache engine |
| 8.47 | Cache expiry per cache type | ✅ Built | `cognitive/reasoning/src/caching/cache.ts`, `control/orchestration/engine/caching/semanticCacheBridge.ts` | Configurable per-cache TTL |
| 8.48 | Budget alerts and graceful degradation *(new)* | ✅ Built | `control/orchestration/engine/governance/budgetTracker.ts`, `engine/fleet/paperclipAdapter.ts` | `BudgetAlert`, threshold warnings, and model downgrade (`tests/budgetAlerts.test.ts`) |
| 8.49 | Shared workspace for parallel agents with locking & conflict checks *(new)* | ✅ Built | `control/orchestration/engine/sharedState/workspace.ts`, `cognitive/action/shared_state/lock_manager.py`, `scratchpad.py` | `SharedWorkspace` + `DistributedLockManager` (`tests/workspace.test.ts`) |
| 8.50 | Collaboration controls: steer/redirect, autonomy level, human handover *(new)* | ✅ Built | `control/orchestration/engine/escalation/humanProtocol.ts`, `engine/fleet/collaborationBridge.ts`, `cognitive/reasoning/src/collaboration/controls.ts` | Tested in `tests/humanProtocol.test.ts` & `tests/collaborationBridge.test.ts` |
