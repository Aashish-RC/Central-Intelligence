# Layer 9: Context Engineering

Context Engineering provides multi-source context synthesis, strict per-tier token budgets, compaction algorithms, and tamper-resistant prompt injection defense.

---

## 1. Core Modules

### `control.context.assembly` (`context_assembler.py`)
- **Multi-Source Synthesis (9.01):** Integrates memory from L2, semantic search results from L3, active tool schemas from L5, and system directives into a unified prompt payload.
- **Token Allocation (9.02):** Enforces hard limits per category (system, memory, knowledge, tools, conversation) preventing memory or large search results from starving executable tool schemas.
- **Prioritization & Pruning (9.03):** When total tokens exceed the context window, drops lower-priority items (knowledge -> memory -> conversation) while strictly preserving system directives and tool schemas.
- **Conversation Compaction (9.04):** Compacts turns beyond the sliding window into bulleted gists using LlamaIndex-aligned history rolling algorithms.
- **Strategy Selector (9.05):** Dynamically chooses between Long Context pass-through and dense Retrieval-Augmented Compaction.

### `control.context.prompts` (`registry.py`, `layering.py`, `templates.py`)
- **Versioned Prompt Registry (9.06):** SemVer-indexed prompt template catalogue.
- **Multi-Tier Layering & Precedence (9.07, 9.10):** Cascading instruction inheritance (User > App > Tenant > Global) with immutable safety directive enforcement.
- **Parameterized Templates (9.08):** Variable substitution with defaults and missing variable validation.
- **A/B Test Hooks (9.09):** Session-hash-partitioned prompt experiment variations feeding into L11 quality metrics.

### `control.context.trust` (`boundary_assembler.py`, `instruction_frame.py`, `untrusted_sandbox.py`, `injection_detector.py`)
- **🚩 Crown Jewel: Dual-Boundary Context Assembler (9.11, 9.12):** Strict separation parser that:
  - Enforces immutable `<system_instruction>` frames models must strictly obey.
  - Encloses all user input, retrieved web documents, memories, and tool outputs into `<untrusted_content source="..." trust="low">` blocks.
  - Injects rigid meta-invariants forbidding execution of instructions inside untrusted blocks.
  - Scans and neutralizes prompt injections ("ignore previous instructions", "system: you are now DAN", delimiter escapes) before delivery.

---

## 2. API Server

FastAPI service located at `control/context/server.py` exposing:
- `POST /v1/context/assemble`: Unified assembly endpoint for L4 Reasoning and external gateway callers.

---

## 3. Testing

Run L9 tests with:
```bash
python -m pytest control/context/tests/ -v
```
