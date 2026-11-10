# Layer 7: Learning, Memory & Continuous Adaptation

Layer 7 coordinates feedback loops, reinforcement learning routing adjustments, graph-native memory, synthetic dataset generation, and demonstration-based capability expansion across Central Intelligence.

## Architecture & Subsystems

### 1. Memory Engines & Knowledge Graphs
- **Cognee Adapter (`cognee/cognee_adapter.py`, Task 7.1)**: Graph-native memory engine supporting `remember`, `recall`, `improve`, and `forget` primitives. Ingests conversational sessions to extract entities, concepts, and relationships into a semantic knowledge graph.
- **LangMem Adapter (`langmem/langmem_adapter.py`, Task 7.2)**: Conversational memory library supporting episodic, semantic, and procedural memory recall, tag indexing, and automated preference extraction.
- **Agenta Adapter (`agenta/agenta_adapter.py`, Task 7.3)**: Team-based agent workspace managing agent definitions, prompt variants, parameter experimentation, and deployment pipelines.

### 2. Reinforcement Learning & Dynamic Routing
- **Routing Weight RL Adjuster (`rl/routing_weight_adjuster.py`, Feature 7.12)**: Continuously shifts candidate model routing weights based on downstream execution reward, evaluator ratings, and user thumbs-up/down feedback. Wires with Layer 8 orchestration policies.

### 3. Synthetic Datasets & Human Labeling
- **Synthetic Dataset Generator (`synthetic/data_generator.py`, Feature 7.28)**: Ingests successful execution traces and transforms them into standardized JSONL fine-tuning datasets formatted for ChatML, OpenAI, and Gemini.
- **Labeling Workflow Queue (`synthetic/labeling_workflow.py`, Feature 7.29)**: Human-in-the-loop review queue allowing annotators to audit, refine, and approve synthetic examples before inclusion in training corpora.

### 4. Privacy, Consent & Adaptation Scopes
- **Consent & Training Lineage (`consent/consent_manager.py` & `consent/lineage_tracker.py`, Features 7.21, 7.22)**: Wires with Layer 10 c15t consent management. Enforces strict per-user opt-in policies, verifies cryptographic data lineage, and supports GDPR "Right to be forgotten" purges.
- **Adaptation Scope Applier (`adaptation/scope_applier.py`, Feature 7.15)**: Enforces strict scoping rules (`USER` -> `APP` -> `PROFESSION` -> `ORG` -> `GLOBAL`), guaranteeing user-level adaptations never bleed across boundaries.
- **Capability Expansion from Demonstration (`demonstration/capability_expander.py`, Features 7.25, 7.26)**: Observes repeated user interaction sequences. Once a recurring workflow is detected 3+ times, automatically synthesizes a candidate skill and requests human review prior to activation.

## Test Verification

```bash
python -m pytest cognitive/learning/ -q -m 'not live'
```
